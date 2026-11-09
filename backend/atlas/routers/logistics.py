"""Logistics & transport analysis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import Settings
from ..connectors import osrm
from ..db import Database
from ..deps import csv_list, get_db, get_settings
from ..identity import require
from ..services import logistics

router = APIRouter(prefix="/api/logistics", tags=["logistics"])


def _lonlat(raw: str) -> tuple[float, float]:
    try:
        lon, lat = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise HTTPException(422, "expected 'lon,lat'") from exc
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise HTTPException(422, "coordinate out of range")
    return lon, lat


@router.get("/nearest", dependencies=[Depends(require("analyst"))])
async def nearest(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    types: str | None = None,
    k: int = Query(5, ge=1, le=25),
    with_routes: bool = False,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    """Closest assets (e.g. hospitals) to a point, optionally with road routes."""
    found = logistics.nearest(db.list_assets(csv_list(types)), lon, lat, k)
    if with_routes:
        for a in found[:5]:  # be polite to the public routing service
            a["route"] = await osrm.route(settings, (lon, lat), (a["lon"], a["lat"]))
    return {"origin": {"lon": lon, "lat": lat}, "results": found}


@router.get("/route", dependencies=[Depends(require("analyst"))])
async def route(
    origin: str = Query(..., alias="from", description="lon,lat"),
    dest: str = Query(..., alias="to", description="lon,lat"),
    settings: Settings = Depends(get_settings),
) -> dict:
    return await osrm.route(settings, _lonlat(origin), _lonlat(dest))


@router.get("/coverage", dependencies=[Depends(require("analyst"))])
def coverage(
    facility_types: str = "hospital",
    demand_types: str | None = None,
    radius_km: float = Query(100.0, gt=0, le=2000),
    db: Database = Depends(get_db),
) -> dict:
    """Which assets are farther than ``radius_km`` from any facility of a type."""
    fac_types = csv_list(facility_types) or ["hospital"]
    facilities = db.list_assets(fac_types)
    demand = [a for a in db.list_assets(csv_list(demand_types)) if a["type"] not in fac_types]
    return logistics.coverage(facilities, demand, radius_km)
