from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import DepartmentOut, ORMModel, WardBrief


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=6, max_length=72)


class UserOut(ORMModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    department: DepartmentOut | None = None
    ward: WardBrief | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    address: str | None = Field(default=None, max_length=500)
