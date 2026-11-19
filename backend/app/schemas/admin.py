from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import DepartmentOut, UTCDateTime, WardBrief


class OfficerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=6, max_length=72, description="Initial password; share it with the officer")
    department_id: int
    ward_id: int


class OfficerUpdate(BaseModel):
    """Send only what changes. Deactivating or moving an officer returns their
    open tickets to the ward queue."""

    is_active: bool | None = None
    department_id: int | None = None
    ward_id: int | None = None


class OfficerOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    is_active: bool
    department: DepartmentOut
    ward: WardBrief
    open_tickets: int  # assigned to them and not yet resolved
    created_at: UTCDateTime
