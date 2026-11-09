"""USGS FDSN earthquake catalogue connector."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

import httpx

from .. import datasets
from ..config import Settings
from ..geo import BBox, in_bbox
from .cache import TTLCache

log = logging.getLogger("atlas.connect.usgs")
_cache = TTLCache(ttl_seconds=300)


def _normalise(raw: dict) -> dict:
    feats = []
    for f in raw.get("features", []):
        p = f.get("properties", {})
        coords = f.get("geometry", {}).get("coordinates", [0, 0, 0])
        ts = p.get("time")
        iso = (
            datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(timespec="seconds")
            if isinstance(ts, (int, float)) else ts
        )
        feats.append({
            "type": "Feature",
            "id": f.get("id"),
            "geometry": {"type": "Point", "coordinates": coords[:3]},
            "properties": {
                "id": f.get("id"),
                "title": p.get("title") or p.get("place"),
                "time": iso,
                "mag": p.get("mag"),
                "depth_km": coords[2] if len(coords) > 2 else None,
                "url": p.get("url"),
                "source": "usgs",
            },
        })
    return {"type": "FeatureCollection", "features": feats}


def historical(bbox: BBox | None, start: date | None, end: date | None, min_mag: float) -> dict:
    fc = datasets.load("earthquakes_historical.geojson")
    out = []
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        p = f["properties"]
        d = datetime.fromisoformat(p["time"].replace("Z", "+00:00")).date()
        if p["mag"] < min_mag:
            continue
        if bbox and not in_bbox(lon, lat, bbox):
            continue
        if start and d < start or end and d > end:
            continue
        out.append(f)
    return {"type": "FeatureCollection", "features": out}


async def fetch_earthquakes(
    settings: Settings,
    bbox: BBox,
    start: date | None = None,
    end: date | None = None,
    min_mag: float = 4.0,
    limit: int = 500,
) -> tuple[dict, str]:
    """Return (FeatureCollection, source) where source is 'usgs' or 'catalogue'."""
    end = end or date.today()
    start = start or end - timedelta(days=365)
    if settings.offline:
        return historical(bbox, start, end, min_mag), "catalogue"
    key = (bbox, start, end, min_mag, limit)
    if (hit := _cache.get(key)) is not None:
        return hit, "usgs"
    west, south, east, north = bbox
    params = {
        "format": "geojson",
        "starttime": start.isoformat(),
        "endtime": (end + timedelta(days=1)).isoformat(),
        "minlatitude": south, "maxlatitude": north,
        "minlongitude": west, "maxlongitude": east,
        "minmagnitude": min_mag,
        "orderby": "time",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(settings.usgs_url, params=params)
            resp.raise_for_status()
            fc = _normalise(resp.json())
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("USGS unavailable (%s); using historical catalogue", exc)
        return historical(bbox, start, end, min_mag), "catalogue"
    _cache.set(key, fc)
    return fc, "usgs"
