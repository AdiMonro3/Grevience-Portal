"""Reference data (categories, departments, wards) and location helpers."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.deps import DB, CurrentUser
from app.models import Category, Department, Ward
from app.schemas.common import CategoryOut, DepartmentOut, WardBrief, WardOut
from app.services import geo

router = APIRouter(tags=["reference data"])


class WardLookup(BaseModel):
    ward: WardBrief | None
    inside_service_area: bool


class GeocodeResult(BaseModel):
    label: str
    lat: float
    lng: float
    ward: WardBrief | None


class ReverseResult(BaseModel):
    address: str | None


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DB):
    return db.scalars(select(Category).order_by(Category.name)).all()


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(db: DB):
    return db.scalars(select(Department).order_by(Department.name)).all()


@router.get("/wards", response_model=list[WardOut])
def list_wards(db: DB):
    return db.scalars(select(Ward).order_by(Ward.code)).all()


@router.get("/geo/ward", response_model=WardLookup)
def ward_for_point(db: DB, lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)):
    ward = geo.find_ward(db, lat, lng)
    return WardLookup(ward=ward, inside_service_area=ward is not None)


@router.get("/geo/geocode", response_model=list[GeocodeResult])
async def geocode(_: CurrentUser, db: DB, q: str = Query(min_length=3, max_length=200)):
    """Typed address -> coordinates (OpenStreetMap). Returns [] when offline."""
    results = await run_in_threadpool(geo.geocode, q)
    return [GeocodeResult(**r, ward=geo.find_ward(db, r["lat"], r["lng"])) for r in results]


@router.get("/geo/reverse", response_model=ReverseResult)
async def reverse(_: CurrentUser, lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180)):
    return ReverseResult(address=await run_in_threadpool(geo.reverse_geocode, lat, lng))
