"""Complaint workflow: submit pipeline, status transitions and history.

Routers and the seed script both go through these functions, so the rules
(who can move a ticket where, what gets logged) live in one place.
"""

from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import utcnow
from app.models import (
    Category,
    Complaint,
    ComplaintHistory,
    ComplaintMedia,
    MediaPurpose,
    Role,
    Status,
    User,
)
from app.services import geo
from app.services.ml import classifier
from app.services.priority import compute_priority
from app.services.storage import SavedFile

# Which status can move to which, and who may do it.
TRANSITIONS: dict[Status, set[Status]] = {
    Status.TRIAGE: {Status.OPEN, Status.REJECTED},
    Status.OPEN: {Status.ASSIGNED, Status.REJECTED},
    Status.ASSIGNED: {Status.IN_PROGRESS, Status.RESOLVED, Status.REJECTED},
    Status.IN_PROGRESS: {Status.RESOLVED, Status.REJECTED},
    Status.RESOLVED: {Status.ASSIGNED, Status.OPEN},  # citizen reopen: back to the officer, or the queue
    Status.REJECTED: set(),
}


def add_history(
    db: Session,
    c: Complaint,
    to_status: str,
    actor: User | None,
    note: str | None = None,
    from_status: str | None = None,
) -> ComplaintHistory:
    row = ComplaintHistory(
        complaint=c,
        from_status=from_status,
        to_status=to_status,
        note=note,
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else "system",
    )
    db.add(row)
    return row


def move(db: Session, c: Complaint, to: Status, actor: User | None, note: str | None = None) -> None:
    current = Status(c.status)
    if to not in TRANSITIONS[current]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot move ticket from {current.value} to {to.value}",
        )
    c.status = to
    c.updated_at = utcnow()
    add_history(db, c, to, actor, note, from_status=current)


def recompute_priority(c: Complaint) -> None:
    weight = c.category.weight if c.category else 1
    c.priority = compute_priority(c.severity, c.urgency, weight, c.upvote_count or 0, c.reopen_count or 0)


def _category_by_code(db: Session, code: str) -> Category | None:
    return db.scalar(select(Category).where(Category.code == code))


def create_complaint(
    db: Session,
    citizen: User,
    description: str,
    severity: str,
    lat: float | None,
    lng: float | None,
    address: str | None,
    media: list[SavedFile],
    created_at=None,  # seed script backdates demo data
) -> Complaint:
    """The whole submit pipeline. Commits and returns the complaint."""
    prediction = classifier.predict(description)
    predicted = _category_by_code(db, prediction.category_code)
    ward = geo.find_ward(db, lat, lng)
    now = created_at or utcnow()

    c = Complaint(
        ticket_no=f"TMP-{now.timestamp()}",  # replaced once we have an id
        created_at=now,
        updated_at=now,
        citizen=citizen,
        description=description.strip(),
        severity=severity,
        lat=lat,
        lng=lng,
        address=address,
        predicted_category=predicted,
        ml_confidence=prediction.confidence,
        urgency=prediction.urgency,
        urgency_reasons=prediction.urgency_reasons,
        upvote_count=0,
        reopen_count=0,
    )

    confident = predicted is not None and prediction.confidence >= settings.ml_confidence_threshold
    reasons = []
    if not confident:
        reasons.append(f"category unclear (confidence {prediction.confidence:.0%})")
    if ward is None:
        reasons.append("location is outside all wards" if lat is not None else "no map location")

    if confident:
        c.category = predicted
        c.department = predicted.department
    c.ward = ward
    c.status = Status.OPEN if not reasons else Status.TRIAGE
    recompute_priority(c)

    for f in media:
        c.media.append(
            ComplaintMedia(
                kind=f.kind,
                purpose=MediaPurpose.REPORT,
                file_name=f.file_name,
                original_name=f.original_name,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
            )
        )

    db.add(c)
    db.flush()  # assigns c.id
    c.ticket_no = f"GRV-{c.created_at:%y}-{c.id:05d}"

    if c.status == Status.OPEN:
        note = f"Auto-routed to {c.department.name}, {ward.name} ({prediction.confidence:.0%} confident)"
    else:
        note = "Sent to manual triage: " + "; ".join(reasons)
    add_history(db, c, "SUBMITTED", citizen, note="Complaint submitted").created_at = now
    add_history(db, c, c.status, None, note=note).created_at = now
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------- officer

def check_jurisdiction(officer: User, c: Complaint) -> None:
    if officer.department_id != c.department_id or officer.ward_id != c.ward_id:
        # 404 rather than 403, so officers can't probe other wards' ticket numbers
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found in your jurisdiction")


def require_assignee(officer: User, c: Complaint) -> None:
    if c.assigned_officer_id != officer.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pick up this ticket before updating it")


def pick(db: Session, officer: User, c: Complaint) -> None:
    move(db, c, Status.ASSIGNED, officer, note=f"Picked up by {officer.name}")
    c.assigned_officer = officer
    c.assigned_at = utcnow()


def set_in_progress(db: Session, officer: User, c: Complaint, note: str | None) -> None:
    require_assignee(officer, c)
    move(db, c, Status.IN_PROGRESS, officer, note=note or "Work started")


def reject(db: Session, actor: User, c: Complaint, reason: str) -> None:
    if actor.role == Role.OFFICER:
        require_assignee(actor, c)
    move(db, c, Status.REJECTED, actor, note=f"Rejected: {reason}")
    c.rejection_reason = reason


def resolve(db: Session, officer: User, c: Complaint, note: str | None, proof: list[SavedFile]) -> None:
    require_assignee(officer, c)
    move(db, c, Status.RESOLVED, officer, note=note or "Resolved")
    c.resolution_note = note
    c.resolved_at = utcnow()
    c.closed_with_proof = bool(proof)
    for f in proof:
        c.media.append(
            ComplaintMedia(
                kind=f.kind,
                purpose=MediaPurpose.PROOF,
                file_name=f.file_name,
                original_name=f.original_name,
                content_type=f.content_type,
                size_bytes=f.size_bytes,
            )
        )


# ---------------------------------------------------------------- citizen reopen

def reopen_blocker(c: Complaint) -> str | None:
    """Why this ticket can't be reopened right now, or None if it can."""
    if c.status != Status.RESOLVED:
        return "Only resolved complaints can be reopened"
    if (c.reopen_count or 0) >= settings.max_reopens:
        return f"This complaint was already reopened {c.reopen_count} times. Please file a new complaint."
    if c.resolved_at and utcnow() - c.resolved_at > timedelta(days=settings.reopen_window_days):
        return f"Complaints can be reopened up to {settings.reopen_window_days} days after they are resolved. Please file a new complaint."
    return None


def reopen(db: Session, citizen: User, c: Complaint, reason: str) -> User | None:
    """The fix didn't work: send the ticket back to the officer who resolved it (or
    to the department queue if that officer is no longer on this ward).
    Returns the officer it went back to, if any."""
    blocker = reopen_blocker(c)
    if blocker:
        raise HTTPException(status.HTTP_409_CONFLICT, blocker)

    officer = c.assigned_officer
    back_to_officer = (
        officer is not None
        and officer.is_active
        and officer.department_id == c.department_id
        and officer.ward_id == c.ward_id
    )
    add_history(db, c, "REOPENED", citizen, note=reason, from_status=c.status)
    if back_to_officer:
        move(db, c, Status.ASSIGNED, None, note=f"Sent back to {officer.name}")
    else:
        move(db, c, Status.OPEN, None, note="Back in the department queue")
        c.assigned_officer, c.assigned_at = None, None

    c.reopen_count = (c.reopen_count or 0) + 1
    c.resolved_at = None
    c.resolution_note = None
    c.closed_with_proof = False  # earlier proof photos stay on the ticket
    recompute_priority(c)
    return officer if back_to_officer else None
