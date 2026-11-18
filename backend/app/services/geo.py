"""Ward lookup, distances and (optional) address geocoding via OpenStreetMap."""

import json
import logging
import math
import ssl
import urllib.parse
import urllib.request

import certifi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Ward

log = logging.getLogger(__name__)
EARTH_RADIUS_KM = 6371.0


def point_in_polygon(lat: float, lng: float, polygon: list[list[float]]) -> bool:
    """Ray casting. `polygon` is a list of [lat, lng] points."""
    inside = False
    n = len(polygon)
    for i in range(n):
        lat1, lng1 = polygon[i]
        lat2, lng2 = polygon[(i + 1) % n]
        if (lng1 > lng) != (lng2 > lng):
            cross_lat = lat1 + (lng - lng1) * (lat2 - lat1) / (lng2 - lng1)
            if lat < cross_lat:
                inside = not inside
    return inside


def find_ward(db: Session, lat: float | None, lng: float | None) -> Ward | None:
    if lat is None or lng is None:
        return None
    for ward in db.scalars(select(Ward)):
        if point_in_polygon(lat, lng, ward.polygon):
            return ward
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Cheap SQL pre-filter before the exact haversine check."""
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


# --- OpenStreetMap Nominatim (needs internet; callers must handle failures) ---

_NOMINATIM = "https://nominatim.openstreetmap.org"
# certifi's CA bundle: python.org builds on macOS ship without system certificates
_SSL = ssl.create_default_context(cafile=certifi.where())


def _nominatim(path: str, params: dict) -> object:
    url = f"{_NOMINATIM}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": settings.geocoder_user_agent})
    with urllib.request.urlopen(req, timeout=6, context=_SSL) as resp:
        return json.load(resp)


def geocode(query: str, limit: int = 5) -> list[dict]:
    try:
        rows = _nominatim(
            "search",
            {
                "q": query,
                "format": "json",
                "limit": limit,
                "countrycodes": "in",
                "viewbox": "77.20,28.75,77.65,28.35",  # prefer Noida / Greater Noida
            },
        )
    except Exception as exc:  # offline on demo day, rate limited, ...
        log.warning("Geocoding failed for %r: %s", query, exc)
        return []
    return [{"label": r["display_name"], "lat": float(r["lat"]), "lng": float(r["lon"])} for r in rows]


def reverse_geocode(lat: float, lng: float) -> str | None:
    try:
        row = _nominatim("reverse", {"lat": lat, "lon": lng, "format": "json", "zoom": 17})
    except Exception as exc:
        log.warning("Reverse geocoding failed: %s", exc)
        return None
    return row.get("display_name") if isinstance(row, dict) else None
