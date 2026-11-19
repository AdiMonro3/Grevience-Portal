from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow
from app.models.enums import Status
from app.models.org import Category, Department, Ward
from app.models.user import User


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_no: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    citizen_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20))  # chosen by the citizen
    lat: Mapped[float | None] = mapped_column(Float, index=True)
    lng: Mapped[float | None] = mapped_column(Float, index=True)
    address: Mapped[str | None] = mapped_column(String(500))

    # Routing
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    predicted_category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    ml_confidence: Mapped[float | None] = mapped_column(Float)
    urgency: Mapped[int] = mapped_column(Integer, default=1)  # 1-3, from the text
    urgency_reasons: Mapped[list] = mapped_column(JSON, default=list)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id"), index=True)

    status: Mapped[str] = mapped_column(String(20), default=Status.OPEN, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)
    upvote_count: Mapped[int] = mapped_column(Integer, default=0)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # by the citizen

    # Officer workflow
    assigned_officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime | None]
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    closed_with_proof: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None]

    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    citizen: Mapped[User] = relationship(foreign_keys=[citizen_id])
    assigned_officer: Mapped[User | None] = relationship(foreign_keys=[assigned_officer_id])
    category: Mapped[Category | None] = relationship(foreign_keys=[category_id])
    predicted_category: Mapped[Category | None] = relationship(foreign_keys=[predicted_category_id])
    department: Mapped[Department | None] = relationship()
    ward: Mapped[Ward | None] = relationship()
    media: Mapped[list["ComplaintMedia"]] = relationship(
        back_populates="complaint", order_by="ComplaintMedia.id", cascade="all, delete-orphan"
    )
    history: Mapped[list["ComplaintHistory"]] = relationship(
        back_populates="complaint", order_by="ComplaintHistory.id", cascade="all, delete-orphan"
    )


class ComplaintMedia(Base):
    __tablename__ = "complaint_media"

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # photo | video
    purpose: Mapped[str] = mapped_column(String(10))  # report | proof
    file_name: Mapped[str] = mapped_column(String(255))  # path relative to MEDIA_DIR
    original_name: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    complaint: Mapped[Complaint] = relationship(back_populates="media")


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str] = mapped_column(String(20), default="system")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    complaint: Mapped[Complaint] = relationship(back_populates="history")
    actor: Mapped[User | None] = relationship()


class Upvote(Base):
    """A citizen saying "Me too" on someone else's complaint."""

    __tablename__ = "upvotes"
    __table_args__ = (UniqueConstraint("complaint_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
