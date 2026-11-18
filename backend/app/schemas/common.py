from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict


def _as_utc(value: datetime) -> datetime:
    # DB stores naive UTC; tag it so the browser shows the right local time.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DepartmentOut(ORMModel):
    id: int
    code: str
    name: str


class WardBrief(ORMModel):
    id: int
    code: str
    name: str


class WardOut(WardBrief):
    center_lat: float
    center_lng: float
    polygon: list[list[float]]


class CategoryBrief(ORMModel):
    id: int
    code: str
    name: str


class CategoryOut(CategoryBrief):
    sla_hours: int
    department: DepartmentOut
