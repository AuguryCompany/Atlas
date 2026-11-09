"""Impact analysis endpoints (analyst role)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import datasets
from ..config import Settings
from ..connectors import firms, usgs
from ..db import Database
from ..deps import bbox_param, csv_list, date_range, get_db, get_settings
from ..identity import require
from ..services import hazards, risk

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class EarthquakeScenario(BaseModel):
    lon: float = Field(..., ge=-180, le=180)
    lat: float = Field(..., ge=-90, le=90)
    magnitude: float = Field(..., ge=3.0, le=9.5)
    min_mmi: float = Field(6.0, ge=1, le=12)
    types: list[str] | None = None


@router.post("/earthquake", dependencies=[Depends(require("analyst"))])
def earthquake_scenario(body: EarthquakeScenario, db: Database = Depends(get_db)) -> dict:
    """Scenario or real-event impact on the asset inventory."""
    assets = db.list_assets(body.types)
    return hazards.earthquake_impact(assets, body.lon, body.lat, body.magnitude, body.min_mmi)


@router.get("/wildfire", dependencies=[Depends(require("analyst"))])
async def wildfire_exposure(
    bbox: str | None = None,
    days: int = Query(2, ge=1, le=10),
    buffer_km: float = Query(10.0, gt=0, le=100),
    types: str | None = None,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    fc, source = await firms.fetch_fires(settings, bbox_param(bbox), days)
    result = hazards.fire_exposure(db.list_assets(csv_list(types)), fc["features"], buffer_km)
    result["source"] = source
    return result


@router.get("/flood", dependencies=[Depends(require("analyst"))])
def flood_exposure(types: str | None = None, db: Database = Depends(get_db)) -> dict:
    zones = datasets.load("flood_zones.geojson")["features"]
    return hazards.flood_exposure(db.list_assets(csv_list(types)), zones)


@router.get("/risk-grid", dependencies=[Depends(require("analyst"))])
async def risk_grid(
    bbox: str | None = None,
    cell_deg: float = Query(0.5, ge=0.1, le=5),
    start: date | None = None,
    end: date | None = None,
    min_mag: float = Query(4.5, ge=0, le=10),
    w_seismic: float = Query(risk.DEFAULT_WEIGHTS["seismic"], ge=0, le=1),
    w_wildfire: float = Query(risk.DEFAULT_WEIGHTS["wildfire"], ge=0, le=1),
    w_flood: float = Query(risk.DEFAULT_WEIGHTS["flood"], ge=0, le=1),
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    area = bbox_param(bbox)
    start, end = date_range(start, end)
    quakes, eq_source = await usgs.fetch_earthquakes(settings, area, start, end, min_mag)
    # Always fold in the reference catalogue so major historical events count.
    ref = usgs.reference(area, None, None, min_mag)["features"]
    fires, fire_source = await firms.fetch_fires(settings, area, 7)
    try:
        grid = risk.compute_grid(
            area, cell_deg, db.list_assets(), quakes["features"] + ref, fires["features"],
            datasets.load("flood_zones.geojson")["features"],
            {"seismic": w_seismic, "wildfire": w_wildfire, "flood": w_flood},
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    grid["metadata"]["sources"] = {"earthquakes": eq_source, "fires": fire_source}
    return grid
