"""Hazard layers (earthquakes, active fires, flood zones) and temporal series."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from .. import datasets
from ..config import Settings
from ..connectors import firms, usgs
from ..db import Database
from ..deps import bbox_param, date_range, get_db, get_settings
from ..geo import feature_collection
from ..identity import require

router = APIRouter(prefix="/api/hazards", tags=["hazards"])


@router.get("/earthquakes", dependencies=[Depends(require("viewer"))])
async def earthquakes(
    bbox: str | None = None,
    start: date | None = None,
    end: date | None = None,
    min_mag: float = Query(4.0, ge=0, le=10),
    settings: Settings = Depends(get_settings),
) -> dict:
    start, end = date_range(start, end)
    fc, source = await usgs.fetch_earthquakes(settings, bbox_param(bbox), start, end, min_mag)
    fc["metadata"] = {"source": source, "count": len(fc["features"])}
    return fc


@router.get("/earthquakes/historical", dependencies=[Depends(require("viewer"))])
def historical_earthquakes() -> dict:
    """Bundled catalogue of major historical earthquakes (always available)."""
    return datasets.load("earthquakes_historical.geojson")


@router.get("/fires", dependencies=[Depends(require("viewer"))])
async def fires(
    bbox: str | None = None,
    days: int = Query(2, ge=1, le=10),
    settings: Settings = Depends(get_settings),
) -> dict:
    fc, source = await firms.fetch_fires(settings, bbox_param(bbox), days)
    fc["metadata"] = {"source": source, "count": len(fc["features"])}
    return fc


@router.get("/floods", dependencies=[Depends(require("viewer"))])
def floods(db: Database = Depends(get_db)) -> dict:
    """Flood hazard zones imported from an authoritative source (e.g. DSİ / AFAD maps)."""
    zones = db.list_zones("flood")
    return feature_collection(zones, count=len(zones))


@router.post("/floods/import", dependencies=[Depends(require("admin"))])
def import_floods(payload: dict = Body(...), db: Database = Depends(get_db)) -> dict:
    """Upsert a GeoJSON FeatureCollection of (Multi)Polygon flood zones.

    Each feature needs ``id``; optional ``name`` and ``level`` (high|medium|low).
    """
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise HTTPException(422, "expected a GeoJSON FeatureCollection")
    try:
        n = db.upsert_zones("flood", payload["features"])
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(422, f"invalid zone: {exc}") from exc
    return {"imported": n}


@router.delete("/floods/{zone_id}", dependencies=[Depends(require("admin"))])
def delete_flood(zone_id: str, db: Database = Depends(get_db)) -> dict:
    if not db.delete_zone("flood", zone_id):
        raise HTTPException(404, "zone not found")
    return {"deleted": zone_id}


@router.get("/earthquakes/timeline", dependencies=[Depends(require("viewer"))])
async def earthquake_timeline(
    bbox: str | None = None,
    start: date | None = None,
    end: date | None = None,
    min_mag: float = Query(4.0, ge=0, le=10),
    bucket: Literal["month", "year"] = "month",
    settings: Settings = Depends(get_settings),
) -> dict:
    """Event counts and peak magnitude per period, for temporal comparison."""
    start, end = date_range(start, end)
    fc, source = await usgs.fetch_earthquakes(settings, bbox_param(bbox), start, end, min_mag)
    series: OrderedDict[str, dict] = OrderedDict()
    for f in sorted(fc["features"], key=lambda f: f["properties"]["time"] or ""):
        t = f["properties"]["time"] or ""
        key = t[:7] if bucket == "month" else t[:4]
        if not key:
            continue
        slot = series.setdefault(key, {"period": key, "count": 0, "max_mag": 0.0})
        slot["count"] += 1
        slot["max_mag"] = max(slot["max_mag"], f["properties"].get("mag") or 0.0)
    return {"source": source, "bucket": bucket, "series": list(series.values())}
