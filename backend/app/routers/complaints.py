from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.deps import DB, Citizen, CurrentUser, get_complaint_or_404
from app.models import Complaint, Role, Severity, Status, Upvote, User
from app.models.enums import ACTIVE_STATUSES, CLOSED_STATUSES
from app.schemas.common import CategoryBrief, DepartmentOut
from app.schemas.complaint import (
    ComplaintDetail,
    ComplaintSummary,
    HistoryOut,
    NearbyItem,
    UpvoteOut,
    to_detail,
    to_history,
    to_summary,
)
from app.services import complaints as workflow
from app.services import email, geo, storage

router = APIRouter(prefix="/complaints", tags=["complaints"])


def ensure_can_view(user: User, c: Complaint) -> None:
    if user.role == Role.ADMIN:
        return
    if user.role == Role.OFFICER:
        workflow.check_jurisdiction(user, c)
    elif c.citizen_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")


@router.post("", response_model=ComplaintDetail, status_code=status.HTTP_201_CREATED)
async def submit_complaint(
    user: Citizen,
    db: DB,
    background: BackgroundTasks,
    description: Annotated[str, Form(min_length=10, max_length=2000)],
    severity: Annotated[Severity, Form()] = Severity.MEDIUM,
    lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Form(ge=-180, le=180)] = None,
    address: Annotated[str | None, Form(max_length=500)] = None,
    photos: Annotated[list[UploadFile] | None, File(description="Up to 3 photos, 5 MB each")] = None,
    video: Annotated[UploadFile | None, File(description="One video, 25 MB max")] = None,
):
    """Submit a complaint. In one request: save media, ML category + urgency,
    ward lookup, triage-or-route, priority, ticket number, history, email."""
    if (lat is None) != (lng is None):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Send both lat and lng, or neither")
    if lat is None and not (address and address.strip()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add your location or an address")

    photos = [p for p in (photos or []) if p.filename]
    video = video if video and video.filename else None
    saved = await storage.save_all(photos, video, "complaints")
    try:
        c = await run_in_threadpool(
            workflow.create_complaint, db, user, description, severity, lat, lng, address, saved
        )
    except BaseException:
        storage.delete_files(saved)
        raise
    email.queue(background, email.complaint_received(c))
    return to_detail(c)


@router.get("/mine", response_model=list[ComplaintSummary])
def my_complaints(user: Citizen, db: DB):
    rows = db.scalars(
        select(Complaint).where(Complaint.citizen_id == user.id).order_by(Complaint.created_at.desc())
    )
    return [to_summary(c) for c in rows]


@router.get("/nearby", response_model=list[NearbyItem])
def nearby(
    user: CurrentUser,
    db: DB,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(3, gt=0, le=20),
    include_resolved: bool = False,
):
    """Complaints around a point. Public fields only (no citizen details)."""
    min_lat, max_lat, min_lng, max_lng = geo.bounding_box(lat, lng, radius_km)
    statuses = [*ACTIVE_STATUSES, Status.RESOLVED] if include_resolved else list(ACTIVE_STATUSES)
    rows = db.scalars(
        select(Complaint).where(
            Complaint.status.in_(statuses),
            Complaint.lat.between(min_lat, max_lat),
            Complaint.lng.between(min_lng, max_lng),
        )
    ).all()
    my_votes = set(
        db.scalars(
            select(Upvote.complaint_id).where(
                Upvote.user_id == user.id, Upvote.complaint_id.in_([c.id for c in rows])
            )
        )
    )
    items = []
    for c in rows:
        distance = geo.haversine_km(lat, lng, c.lat, c.lng)
        if distance > radius_km:
            continue
        items.append(
            NearbyItem(
                ticket_no=c.ticket_no,
                description=c.description,
                status=c.status,
                category=CategoryBrief.model_validate(c.category) if c.category else None,
                department=DepartmentOut.model_validate(c.department) if c.department else None,
                address=c.address,
                lat=c.lat,
                lng=c.lng,
                distance_km=round(distance, 2),
                upvote_count=c.upvote_count,
                thumbnail_url=to_summary(c).thumbnail_url,
                created_at=c.created_at,
                mine=c.citizen_id == user.id,
                i_upvoted=c.id in my_votes,
            )
        )
    items.sort(key=lambda i: i.distance_km)
    return items[:100]


@router.get("/{ticket_no}", response_model=ComplaintDetail)
def get_complaint(ticket_no: str, user: CurrentUser, db: DB):
    c = get_complaint_or_404(db, ticket_no)
    ensure_can_view(user, c)
    return to_detail(c, include_citizen=user.role != Role.CITIZEN)


@router.get("/{ticket_no}/history", response_model=list[HistoryOut])
def get_history(ticket_no: str, user: CurrentUser, db: DB):
    c = get_complaint_or_404(db, ticket_no)
    ensure_can_view(user, c)
    return to_history(c)


@router.post("/{ticket_no}/upvote", response_model=UpvoteOut)
def upvote(ticket_no: str, user: Citizen, db: DB):
    """"Me too" on someone else's complaint. Raises its priority. Idempotent."""
    c = get_complaint_or_404(db, ticket_no)
    if c.citizen_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You reported this complaint yourself")
    if c.status in CLOSED_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "This complaint is already closed")
    already = db.scalar(select(Upvote).where(Upvote.complaint_id == c.id, Upvote.user_id == user.id))
    if not already:
        db.add(Upvote(complaint_id=c.id, user_id=user.id))
        c.upvote_count += 1
        workflow.recompute_priority(c)
        db.commit()
    return UpvoteOut(ticket_no=c.ticket_no, upvote_count=c.upvote_count, priority=c.priority)
