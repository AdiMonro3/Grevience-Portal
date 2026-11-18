from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(300))

    categories: Mapped[list["Category"]] = relationship(back_populates="department")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # = ML label
    name: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    weight: Mapped[int] = mapped_column(Integer, default=1)  # 0-2, how serious by nature
    sla_hours: Mapped[int] = mapped_column(Integer, default=72)  # used in Phase 3 escalation

    department: Mapped[Department] = relationship(back_populates="categories")


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Boundary as a list of [lat, lng] points. Demo uses rough rectangles;
    # Phase 3 swaps in real shapes (shapely) without changing the column.
    polygon: Mapped[list] = mapped_column(JSON)
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
