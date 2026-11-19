"""Minimal admin for the demo: route triage tickets by hand (full CRUD is Phase 3)."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import select

from app.deps import DB, Admin, get_complaint_or_404
from app.models import Category, Complaint, Department, Status, Ward
from app.schemas.complaint import AdminRejectIn, AssignIn, ComplaintDetail, to_detail
from app.services import complaints as workflow
from app.services import email

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/triage", response_model=list[ComplaintDetail])
def triage_queue(_: Admin, db: DB):
    """Tickets the ML wasn't sure about, or outside every ward. Oldest first."""
    rows = db.scalars(
        select(Complaint).where(Complaint.status == Status.TRIAGE).order_by(Complaint.created_at.asc())
    )
    return [to_detail(c, include_citizen=True) for c in rows]


@router.patch("/complaints/{ticket_no}/assign", response_model=ComplaintDetail)
def assign(ticket_no: str, body: AssignIn, admin: Admin, db: DB, background: BackgroundTasks):
    """Route a triage ticket to a department + ward (optionally fixing the category)."""
    c = get_complaint_or_404(db, ticket_no)
    if c.status != Status.TRIAGE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only tickets in triage can be routed (this one is {c.status})")
    department = db.get(Department, body.department_id)
    ward = db.get(Ward, body.ward_id)
    if department is None or ward is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown department or ward")

    if body.category_id is not None:
        category = db.get(Category, body.category_id)
        if category is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category")
        if category.department_id != department.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"'{category.name}' belongs to another department"
            )
    elif c.predicted_category and c.predicted_category.department_id == department.id:
        category = c.predicted_category  # admin agreed with the model's guess
    else:
        category = None

    note = f"Routed by admin to {department.name}, {ward.name}"
    if category:
        note += f" as '{category.name}'"
    workflow.move(db, c, Status.OPEN, admin, note=note)
    c.category, c.department, c.ward = category, department, ward
    workflow.recompute_priority(c)
    db.commit()
    email.queue(background, email.complaint_routed(c))
    return to_detail(c, include_citizen=True)


@router.post("/complaints/{ticket_no}/reject", response_model=ComplaintDetail)
def reject(ticket_no: str, body: AdminRejectIn, admin: Admin, db: DB, background: BackgroundTasks):
    """Close spam / duplicates straight from triage."""
    c = get_complaint_or_404(db, ticket_no)
    workflow.reject(db, admin, c, body.reason.strip())
    db.commit()
    email.queue(background, email.status_changed(c))
    return to_detail(c, include_citizen=True)
