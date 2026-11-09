"""Critical infrastructure inventory."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException

from ..db import Database, asset_to_feature
from ..deps import bbox_param, csv_list, get_db
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
    "other": "Other",
}


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


