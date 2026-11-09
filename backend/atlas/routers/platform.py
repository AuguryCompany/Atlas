"""Platform endpoints: health, identity, imagery catalogue, audit trail."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import __version__
from ..config import Settings
from ..db import Database
from ..deps import DEFAULT_BBOX, get_db, get_settings
from ..identity import Principal, require, resolve_principal
from ..services import imagery

router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "product": "Augury Atlas",
        "version": __version__,
        "offline": settings.offline,
        "connectors": {
            "usgs": "reference" if settings.offline else "live",
            "firms": "live" if settings.firms_map_key and not settings.offline else "reference",
            "osrm": "estimate" if settings.offline else "live",
        },
        "default_bbox": DEFAULT_BBOX,
    }


@router.get("/me")
def me(principal: Principal = Depends(resolve_principal)) -> dict:
    return {"name": principal.name, "role": principal.role}


@router.get("/imagery", dependencies=[Depends(require("viewer"))])
def imagery_catalogue() -> dict:
    return imagery.catalogue()


@router.get("/audit", dependencies=[Depends(require("admin"))])
def audit(limit: int = Query(100, ge=1, le=1000), db: Database = Depends(get_db)) -> list[dict]:
    return db.list_audit(limit)
