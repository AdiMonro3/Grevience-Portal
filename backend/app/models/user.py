from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow
from app.models.enums import Role
from app.models.org import Department, Ward


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.CITIZEN, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Officers only: their jurisdiction
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"))

    # Citizens: last saved location
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    department: Mapped[Department | None] = relationship()
    ward: Mapped[Ward | None] = relationship()
