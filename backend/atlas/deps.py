"""Shared FastAPI dependencies and query parsing helpers."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, Request

from .config import Settings
from .db import Database
from .geo import BBox, parse_bbox

# Default area of interest: Türkiye and immediate surroundings.
DEFAULT_BBOX: BBox = (25.5, 35.5, 45.0, 42.5)


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def bbox_param(raw: str | None) -> BBox:
    try:
        return parse_bbox(raw) or DEFAULT_BBOX
    except ValueError as exc:
        raise HTTPException(422, f"invalid bbox: {exc}") from exc


def date_range(start: date | None, end: date | None) -> tuple[date | None, date | None]:
    if start and end and start > end:
        raise HTTPException(422, "start must be before end")
    return start, end


def csv_list(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    items = [p.strip() for p in raw.split(",") if p.strip()]
    return items or None
