"""Admin: route triage tickets, manage officers. (Departments/wards/categories CRUD: Phase 3.)"""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import func, select

from app.deps import DB, Admin, get_complaint_or_404
from app.models import Category, Complaint, Department, Role, Status, User, Ward
from app.schemas.admin import OfficerIn, OfficerOut, OfficerUpdate
from app.schemas.complaint import AdminRejectIn, AssignIn, ComplaintDetail, to_detail
from app.services import complaints as workflow
from app.security import hash_password
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


# ---------------------------------------------------------------- officers

WORKING = (Status.ASSIGNED, Status.IN_PROGRESS)


def _open_ticket_counts(db, officer_ids: list[int]) -> dict[int, int]:
    rows = db.execute(
        select(Complaint.assigned_officer_id, func.count())
        .where(Complaint.assigned_officer_id.in_(officer_ids), Complaint.status.in_(WORKING))
        .group_by(Complaint.assigned_officer_id)
    )
    return dict(rows.all())


def _officer_out(officer: User, open_tickets: int) -> OfficerOut:
    return OfficerOut(
        id=officer.id,
        name=officer.name,
        email=officer.email,
        phone=officer.phone,
        is_active=officer.is_active,
        department=officer.department,
        ward=officer.ward,
        open_tickets=open_tickets,
        created_at=officer.created_at,
    )


def _check_jurisdiction_ids(db, department_id: int, ward_id: int) -> None:
    if db.get(Department, department_id) is None or db.get(Ward, ward_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown department or ward")


@router.get("/officers", response_model=list[OfficerOut])
def list_officers(_: Admin, db: DB, department_id: int | None = None, ward_id: int | None = None):
    """All officers (active and inactive), by ward then department."""
    q = (
        select(User)
        .join(Ward, User.ward_id == Ward.id)
        .join(Department, User.department_id == Department.id)
        .where(User.role == Role.OFFICER)
        .order_by(Ward.code, Department.name, User.name)
    )
    if department_id is not None:
        q = q.where(User.department_id == department_id)
    if ward_id is not None:
        q = q.where(User.ward_id == ward_id)
    officers = list(db.scalars(q))
    counts = _open_ticket_counts(db, [o.id for o in officers])
    return [_officer_out(o, counts.get(o.id, 0)) for o in officers]


@router.post("/officers", response_model=OfficerOut, status_code=status.HTTP_201_CREATED)
def create_officer(body: OfficerIn, _: Admin, db: DB):
    """Add an officer for a department + ward. They log in with this email and password."""
    email_addr = body.email.lower()
    if db.scalar(select(User).where(User.email == email_addr)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    _check_jurisdiction_ids(db, body.department_id, body.ward_id)
    officer = User(
        name=body.name.strip(),
        email=email_addr,
        phone=body.phone or None,
        password_hash=hash_password(body.password),
        role=Role.OFFICER,
        department_id=body.department_id,
        ward_id=body.ward_id,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    return _officer_out(officer, 0)


@router.patch("/officers/{officer_id}", response_model=OfficerOut)
def update_officer(officer_id: int, body: OfficerUpdate, admin: Admin, db: DB):
    """Activate / deactivate, or move to another department or ward.
    Their picked-up tickets go back to the ward queue, since they can no longer work on them."""
    officer = db.get(User, officer_id)
    if officer is None or officer.role != Role.OFFICER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Officer not found")

    department_id = body.department_id if body.department_id is not None else officer.department_id
    ward_id = body.ward_id if body.ward_id is not None else officer.ward_id
    moved = (department_id, ward_id) != (officer.department_id, officer.ward_id)
    if moved:
        _check_jurisdiction_ids(db, department_id, ward_id)
    deactivated = body.is_active is False and officer.is_active

    if moved or deactivated:
        note = "Returned to queue: " + ("officer deactivated" if deactivated else "officer moved to another ward")
        tickets = db.scalars(
            select(Complaint).where(Complaint.assigned_officer_id == officer.id, Complaint.status.in_(WORKING))
        ).all()
        for c in tickets:
            workflow.unassign(db, admin, c, note)

    officer.department_id, officer.ward_id = department_id, ward_id
    if body.is_active is not None:
        officer.is_active = body.is_active
    db.commit()
    db.refresh(officer)
    return _officer_out(officer, _open_ticket_counts(db, [officer.id]).get(officer.id, 0))
