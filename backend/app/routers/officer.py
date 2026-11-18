"""Officer workflow. Every endpoint checks the ticket is in the officer's
department + ward (jurisdiction) before doing anything."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select

from app.deps import DB, Officer, get_complaint_or_404
from app.models import Complaint, Status
from app.schemas.complaint import ComplaintDetail, ComplaintSummary, StatusUpdateIn, to_detail, to_summary
from app.services import complaints as workflow
from app.services import email, storage

router = APIRouter(prefix="/officer", tags=["officer"])


def _load(db, officer, ticket_no: str) -> Complaint:
    c = get_complaint_or_404(db, ticket_no)
    workflow.check_jurisdiction(officer, c)
    return c


@router.get("/queue", response_model=list[ComplaintSummary])
def queue(officer: Officer, db: DB, status_filter: Annotated[list[Status] | None, Query(alias="status")] = None):
    """Tickets in my department + ward: highest priority first, then oldest first."""
    q = select(Complaint).where(
        Complaint.department_id == officer.department_id,
        Complaint.ward_id == officer.ward_id,
    )
    if status_filter:
        q = q.where(Complaint.status.in_(status_filter))
    q = q.order_by(Complaint.priority.desc(), Complaint.created_at.asc())
    return [to_summary(c) for c in db.scalars(q)]


@router.get("/complaints/{ticket_no}", response_model=ComplaintDetail)
def get_ticket(ticket_no: str, officer: Officer, db: DB):
    return to_detail(_load(db, officer, ticket_no), include_citizen=True)


@router.post("/complaints/{ticket_no}/pick", response_model=ComplaintDetail)
def pick(ticket_no: str, officer: Officer, db: DB, background: BackgroundTasks):
    c = _load(db, officer, ticket_no)
    if c.assigned_officer_id == officer.id:
        return to_detail(c, include_citizen=True)
    if c.status != Status.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ticket is {c.status}, only OPEN tickets can be picked")
    workflow.pick(db, officer, c)
    db.commit()
    email.queue(background, email.officer_assigned(c, officer))
    return to_detail(c, include_citizen=True)


@router.patch("/complaints/{ticket_no}/status", response_model=ComplaintDetail)
def update_status(ticket_no: str, body: StatusUpdateIn, officer: Officer, db: DB, background: BackgroundTasks):
    """Move to IN_PROGRESS (optional note in `reason`) or REJECTED (`reason` required)."""
    c = _load(db, officer, ticket_no)
    if body.status == Status.IN_PROGRESS:
        workflow.set_in_progress(db, officer, c, body.reason)
    else:
        workflow.reject(db, officer, c, body.reason.strip())
    db.commit()
    email.queue(background, email.status_changed(c))
    return to_detail(c, include_citizen=True)


@router.post("/complaints/{ticket_no}/resolve", response_model=ComplaintDetail)
async def resolve(
    ticket_no: str,
    officer: Officer,
    db: DB,
    background: BackgroundTasks,
    note: Annotated[str | None, Form(max_length=2000)] = None,
    photos: Annotated[list[UploadFile] | None, File(description="Proof photos (optional)")] = None,
    video: Annotated[UploadFile | None, File(description="Proof video (optional)")] = None,
):
    c = _load(db, officer, ticket_no)
    # Check before writing files so a refused request leaves nothing on disk
    workflow.require_assignee(officer, c)
    if Status.RESOLVED not in workflow.TRANSITIONS[Status(c.status)]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ticket is {c.status} and cannot be resolved")

    photos = [p for p in (photos or []) if p.filename]
    video = video if video and video.filename else None
    saved = await storage.save_all(photos, video, "proof")
    try:
        workflow.resolve(db, officer, c, note.strip() if note else None, saved)
        db.commit()
    except BaseException:
        db.rollback()
        storage.delete_files(saved)
        raise
    email.queue(background, email.resolved(c))
    return to_detail(c, include_citizen=True)
