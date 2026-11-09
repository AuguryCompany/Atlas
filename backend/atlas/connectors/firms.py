"""NASA FIRMS active-fire connector (requires a free FIRMS MAP_KEY)."""

from __future__ import annotations

import csv
import io
import logging

import httpx

from ..config import Settings
from ..geo import BBox
from .cache import TTLCache

log = logging.getLogger("atlas.connect.firms")
_cache = TTLCache(ttl_seconds=900)
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{sensor}/{area}/{days}"


def empty() -> dict:
    return {"type": "FeatureCollection", "features": []}


def _parse_csv(text: str) -> dict:
    feats = []
    for i, row in enumerate(csv.DictReader(io.StringIO(text))):
        try:
            lon, lat = float(row["longitude"]), float(row["latitude"])
        except (KeyError, ValueError):
            continue
        fid = f"FIRMS-{i}"
        feats.append({
            "type": "Feature",
            "id": fid,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": fid,
                "acq_date": row.get("acq_date"),
                "acq_time": row.get("acq_time"),
                "frp": float(row["frp"]) if row.get("frp") else None,
                "confidence": row.get("confidence"),
                "source": "firms",
            },
        })
    return {"type": "FeatureCollection", "features": feats}


async def fetch_fires(
    settings: Settings, bbox: BBox, days: int = 2, sensor: str = "VIIRS_SNPP_NRT"
) -> tuple[dict, str]:
    """Return (FeatureCollection, source); source is 'firms' or 'unavailable'.

    There is deliberately no synthetic fallback: without a FIRMS key or
    connectivity the layer is empty and the source says so.
    """
    if settings.offline or not settings.firms_map_key:
        return empty(), "unavailable"
    days = max(1, min(days, 10))
    key = (bbox, days, sensor)
    if (hit := _cache.get(key)) is not None:
        return hit, "firms"
    area = ",".join(str(v) for v in bbox)
    url = FIRMS_URL.format(key=settings.firms_map_key, sensor=sensor, area=area, days=days)
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            fc = _parse_csv(resp.text)
    except httpx.HTTPError as exc:
        log.warning("FIRMS unavailable (%s)", exc)
        return empty(), "unavailable"
    _cache.set(key, fc)
    return fc, "firms"
