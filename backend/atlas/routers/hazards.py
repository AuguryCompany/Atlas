"""Hazard layers (earthquakes, active fires, flood zones) and temporal series."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from .. import datasets
from ..config import Settings
from ..connectors import firms, usgs
from ..deps import bbox_param, date_range, get_settings
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


@router.get("/earthquakes/reference", dependencies=[Depends(require("viewer"))])
def reference_earthquakes() -> dict:
    """Bundled catalogue of major historical events (always available)."""
    return datasets.load("earthquakes_reference.geojson")


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
def floods() -> dict:
    return datasets.load("flood_zones.geojson")


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
