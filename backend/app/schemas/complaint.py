from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models import Complaint, MediaPurpose, User
from app.schemas.common import CategoryBrief, DepartmentOut, UTCDateTime, WardBrief
from app.services.complaints import reopen_blocker
from app.services.priority import priority_label
from app.services.storage import media_url


class MediaOut(BaseModel):
    id: int
    kind: str
    purpose: str
    url: str
    content_type: str | None
    size_bytes: int


class HistoryOut(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    note: str | None
    actor_name: str | None
    actor_role: str
    created_at: UTCDateTime


class PersonBrief(BaseModel):
    name: str
    email: str
    phone: str | None


class ComplaintSummary(BaseModel):
    ticket_no: str
    description: str
    severity: str
    status: str
    priority: int
    priority_label: str
    urgency: int
    category: CategoryBrief | None
    department: DepartmentOut | None
    ward: WardBrief | None
    address: str | None
    lat: float | None
    lng: float | None
    upvote_count: int
    reopen_count: int
    thumbnail_url: str | None
    assigned_officer_name: str | None
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ComplaintDetail(ComplaintSummary):
    predicted_category: CategoryBrief | None
    ml_confidence: float | None
    urgency_reasons: list[str]
    assigned_officer: PersonBrief | None
    assigned_at: UTCDateTime | None
    rejection_reason: str | None
    resolution_note: str | None
    closed_with_proof: bool
    resolved_at: UTCDateTime | None
    can_reopen: bool  # resolved, inside the reopen window, reopens left
    media: list[MediaOut]
    history: list[HistoryOut]
    citizen: PersonBrief | None = None  # only shown to officers/admins


class NearbyItem(BaseModel):
    """Public view: no citizen name, email or phone."""

    ticket_no: str
    description: str
    status: str
    category: CategoryBrief | None
    department: DepartmentOut | None
    address: str | None
    lat: float
    lng: float
    distance_km: float
    upvote_count: int
    thumbnail_url: str | None
    created_at: UTCDateTime
    mine: bool
    i_upvoted: bool


class UpvoteOut(BaseModel):
    ticket_no: str
    upvote_count: int
    priority: int
    i_upvoted: bool = True


class StatusUpdateIn(BaseModel):
    status: Literal["IN_PROGRESS", "REJECTED"]
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def reason_required_for_reject(self):
        if self.status == "REJECTED" and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required to reject a complaint")
        return self


class AssignIn(BaseModel):
    department_id: int
    ward_id: int
    category_id: int | None = None


class ReopenIn(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)] = Field(
        description="What is still wrong"
    )


class AdminRejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


# ---------------------------------------------------------------- builders

def _person(user: User | None) -> PersonBrief | None:
    return PersonBrief(name=user.name, email=user.email, phone=user.phone) if user else None


def _thumbnail(c: Complaint) -> str | None:
    for m in c.media:
        if m.purpose == MediaPurpose.REPORT and m.kind == "photo":
            return media_url(m.file_name)
    return None


def _summary_fields(c: Complaint) -> dict:
    return dict(
        ticket_no=c.ticket_no,
        description=c.description,
        severity=c.severity,
        status=c.status,
        priority=c.priority,
        priority_label=priority_label(c.priority),
        urgency=c.urgency,
        category=CategoryBrief.model_validate(c.category) if c.category else None,
        department=DepartmentOut.model_validate(c.department) if c.department else None,
        ward=WardBrief.model_validate(c.ward) if c.ward else None,
        address=c.address,
        lat=c.lat,
        lng=c.lng,
        upvote_count=c.upvote_count,
        reopen_count=c.reopen_count or 0,
        thumbnail_url=_thumbnail(c),
        assigned_officer_name=c.assigned_officer.name if c.assigned_officer else None,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def to_summary(c: Complaint) -> ComplaintSummary:
    return ComplaintSummary(**_summary_fields(c))


def to_detail(c: Complaint, include_citizen: bool = False) -> ComplaintDetail:
    return ComplaintDetail(
        **_summary_fields(c),
        predicted_category=CategoryBrief.model_validate(c.predicted_category) if c.predicted_category else None,
        ml_confidence=c.ml_confidence,
        urgency_reasons=c.urgency_reasons or [],
        assigned_officer=_person(c.assigned_officer),
        assigned_at=c.assigned_at,
        rejection_reason=c.rejection_reason,
        resolution_note=c.resolution_note,
        closed_with_proof=c.closed_with_proof,
        resolved_at=c.resolved_at,
        can_reopen=reopen_blocker(c) is None,
        media=[
            MediaOut(
                id=m.id,
                kind=m.kind,
                purpose=m.purpose,
                url=media_url(m.file_name),
                content_type=m.content_type,
                size_bytes=m.size_bytes,
            )
            for m in c.media
        ],
        history=to_history(c),
        citizen=_person(c.citizen) if include_citizen else None,
    )


def to_history(c: Complaint) -> list[HistoryOut]:
    return [
        HistoryOut(
            id=h.id,
            from_status=h.from_status,
            to_status=h.to_status,
            note=h.note,
            actor_name=h.actor.name if h.actor else None,
            actor_role=h.actor_role,
            created_at=h.created_at,
        )
        for h in c.history
    ]
