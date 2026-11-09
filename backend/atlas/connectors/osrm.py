"""OSRM road-routing connector with a great-circle fallback."""

from __future__ import annotations

import logging

import httpx

from ..config import Settings
from ..geo import haversine_km

log = logging.getLogger("atlas.connect.osrm")

# Fallback model: roads are ~30% longer than the straight line, 70 km/h average.
DETOUR_FACTOR = 1.3
FALLBACK_SPEED_KMH = 70.0


def estimate(origin: tuple[float, float], dest: tuple[float, float]) -> dict:
    km = haversine_km(*origin, *dest) * DETOUR_FACTOR
    return {
        "distance_km": round(km, 2),
        "duration_min": round(km / FALLBACK_SPEED_KMH * 60, 1),
        "geometry": {"type": "LineString", "coordinates": [list(origin), list(dest)]},
        "source": "estimate",
    }


async def route(
    settings: Settings, origin: tuple[float, float], dest: tuple[float, float]
) -> dict:
    if settings.offline:
        return estimate(origin, dest)
    coords = f"{origin[0]},{origin[1]};{dest[0]},{dest[1]}"
    url = f"{settings.osrm_url.rstrip('/')}/route/v1/driving/{coords}"
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(url, params={"overview": "simplified", "geometries": "geojson"})
            resp.raise_for_status()
            data = resp.json()
        best = data["routes"][0]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("OSRM unavailable (%s); using straight-line estimate", exc)
        return estimate(origin, dest)
    return {
        "distance_km": round(best["distance"] / 1000, 2),
        "duration_min": round(best["duration"] / 60, 1),
        "geometry": best["geometry"],
        "source": "osrm",
    }
