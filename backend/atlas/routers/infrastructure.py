"""Critical infrastructure inventory."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import Settings
from ..connectors import overpass
from ..db import Database, asset_to_feature
from ..deps import bbox_param, csv_list, get_db, get_settings
from ..geo import feature_collection, in_bbox
from ..identity import require

router = APIRouter(prefix="/api/infrastructure", tags=["infrastructure"])

ASSET_TYPES = {
    "airport": "Airport",
    "port": "Port",
    "bridge": "Bridge",
    "dam": "Dam / HPP",
    "power_plant": "Power plant",
    "energy": "Energy (refinery / terminal)",
    "hospital": "Hospital",
    "substation": "Substation",
    "other": "Other",
}


class OsmImport(BaseModel):
    categories: list[str] = Field(default_factory=lambda: ["airport", "port", "hospital"])
    bbox: str | None = Field(None, description="west,south,east,north; omit to use the whole country")
    country: str = Field("TR", min_length=2, max_length=2)


@router.get("/osm/categories", dependencies=[Depends(require("viewer"))])
def osm_categories() -> dict:
    return {k: c.label for k, c in overpass.CATEGORIES.items()}


@router.post("/import/osm", dependencies=[Depends(require("admin"))])
async def import_osm(
    body: OsmImport,
    settings: Settings = Depends(get_settings),
    db: Database = Depends(get_db),
) -> dict:
    """Discover real infrastructure from OpenStreetMap and upsert it into the inventory."""
    area = bbox_param(body.bbox) if body.bbox else None
    try:
        feats = await overpass.fetch_infrastructure(settings, body.categories, area, body.country.upper())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except overpass.OverpassError as exc:
        raise HTTPException(502, str(exc)) from exc
    n = db.upsert_features(feats)
    by_type: dict[str, int] = {}
    for f in feats:
        t = f["properties"]["type"]
        by_type[t] = by_type.get(t, 0) + 1
    return {"imported": n, "by_type": by_type, "source": "OpenStreetMap (ODbL)"}


@router.get("/types", dependencies=[Depends(require("viewer"))])
def list_types() -> dict:
    return ASSET_TYPES


@router.get("", dependencies=[Depends(require("viewer"))])
def list_assets(
    types: str | None = None,
    bbox: str | None = None,
    min_criticality: int = 1,
    db: Database = Depends(get_db),
) -> dict:
    assets = db.list_assets(csv_list(types))
    area = bbox_param(bbox) if bbox else None
    feats = [
        asset_to_feature(a)
        for a in assets
        if a["criticality"] >= min_criticality and (area is None or in_bbox(a["lon"], a["lat"], area))
    ]
    return feature_collection(feats, count=len(feats))


@router.get("/{asset_id}", dependencies=[Depends(require("viewer"))])
def get_asset(asset_id: str, db: Database = Depends(get_db)) -> dict:
    asset = db.get_asset(asset_id)
    if not asset:
        raise HTTPException(404, "asset not found")
    return asset_to_feature(asset)


@router.post("/import", dependencies=[Depends(require("admin"))])
def import_assets(payload: dict = Body(...), db: Database = Depends(get_db)) -> dict:
    """Upsert a GeoJSON FeatureCollection of Point assets (AUGURY CORE ingestion)."""
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise HTTPException(422, "expected a GeoJSON FeatureCollection")
    try:
        n = db.upsert_features(payload["features"])
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise HTTPException(422, f"invalid feature: {exc}") from exc
    return {"imported": n}


@router.delete("/{asset_id}", dependencies=[Depends(require("admin"))])
def delete_asset(asset_id: str, db: Database = Depends(get_db)) -> dict:
    if not db.delete_asset(asset_id):
        raise HTTPException(404, "asset not found")
    return {"deleted": asset_id}


