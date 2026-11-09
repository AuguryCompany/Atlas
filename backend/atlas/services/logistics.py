"""Logistics & transport: nearest facilities and service-area coverage."""

from __future__ import annotations

from ..geo import haversine_km


def nearest(assets: list[dict], lon: float, lat: float, k: int = 5) -> list[dict]:
    ranked = sorted(
        ({**a, "distance_km": round(haversine_km(lon, lat, a["lon"], a["lat"]), 2)} for a in assets),
        key=lambda a: a["distance_km"],
    )
    return ranked[:k]


def coverage(
    facilities: list[dict], demand_points: list[dict], radius_km: float
) -> dict:
    """Which demand points (e.g. other assets) lie outside every facility's radius."""
    uncovered = []
    for d in demand_points:
        best = min(
            (haversine_km(d["lon"], d["lat"], f["lon"], f["lat"]) for f in facilities),
            default=float("inf"),
        )
        if best > radius_km:
            uncovered.append({**d, "nearest_facility_km": round(best, 1) if best != float("inf") else None})
    total = len(demand_points)
    return {
        "radius_km": radius_km,
        "facilities": len(facilities),
        "demand_points": total,
        "covered": total - len(uncovered),
        "coverage_ratio": round((total - len(uncovered)) / total, 3) if total else 1.0,
        "uncovered": uncovered,
    }
