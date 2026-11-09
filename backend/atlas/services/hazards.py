"""Earthquake, wildfire and flood impact analysis against the asset inventory."""

from __future__ import annotations

import math

from ..geo import circle_polygon, haversine_km, point_in_geometry

# Atkinson & Wald (2007) intensity prediction equation, California coefficients.
# MMI = c1 + c2(M-6) + c3(M-6)^2 + c4 log10 R + c5 R + c6 B + c7 M log10 R
# with R = sqrt(D^2 + 14^2) (km) and B = max(0, log10(R/50)).
_AW07 = (12.27, 2.270, 0.1304, -1.30, -0.0007070, 1.95, -0.577)

DAMAGE_STATES = [  # (min MMI, label) — highest first
    (9.0, "severe"),
    (8.0, "heavy"),
    (7.0, "moderate"),
    (6.0, "light"),
    (0.0, "none"),
]


def rupture_length_km(magnitude: float) -> float:
    """Wells & Coppersmith (1994) surface rupture length, all slip types."""
    return 10 ** (-3.22 + 0.69 * magnitude)


def estimate_mmi(magnitude: float, distance_km: float, finite_fault: bool = True) -> float:
    """Estimated Modified Mercalli Intensity at an epicentral distance.

    A point source badly underestimates shaking for large events whose rupture
    spans hundreds of kilometres, so by default the epicentral distance is
    reduced by half the expected rupture length (strike unknown, so the
    correction is isotropic). This is a screening approximation.
    """
    c1, c2, c3, c4, c5, c6, c7 = _AW07
    if finite_fault:
        distance_km = max(0.0, distance_km - rupture_length_km(magnitude) / 2)
    r = math.sqrt(distance_km**2 + 14.0**2)
    log_r = math.log10(r)
    b = max(0.0, math.log10(r / 50.0))
    m = magnitude - 6.0
    mmi = c1 + c2 * m + c3 * m * m + c4 * log_r + c5 * r + c6 * b + c7 * magnitude * log_r
    return max(1.0, min(12.0, mmi))


def damage_state(mmi: float) -> str:
    for threshold, label in DAMAGE_STATES:
        if mmi >= threshold:
            return label
    return "none"


def radius_for_mmi(magnitude: float, target_mmi: float, max_km: float = 1000.0) -> float:
    """Epicentral distance at which estimated MMI falls to ``target_mmi`` (bisection)."""
    if estimate_mmi(magnitude, 0.0) < target_mmi:
        return 0.0
    lo, hi = 0.0, max_km
    if estimate_mmi(magnitude, hi) >= target_mmi:
        return hi
    for _ in range(40):
        mid = (lo + hi) / 2
        if estimate_mmi(magnitude, mid) >= target_mmi:
            lo = mid
        else:
            hi = mid
    return round(lo, 1)


def _summarise(impacted: list[dict], key: str) -> dict:
    by_type: dict[str, int] = {}
    by_level: dict[str, int] = {}
    for a in impacted:
        by_type[a["type"]] = by_type.get(a["type"], 0) + 1
        by_level[a[key]] = by_level.get(a[key], 0) + 1
    return {
        "assets_affected": len(impacted),
        "critical_assets_affected": sum(1 for a in impacted if a["criticality"] >= 4),
        "by_type": by_type,
        f"by_{key}": by_level,
    }


def earthquake_impact(
    assets: list[dict], lon: float, lat: float, magnitude: float, min_mmi: float = 6.0
) -> dict:
    impacted = []
    for a in assets:
        dist = haversine_km(lon, lat, a["lon"], a["lat"])
        mmi = estimate_mmi(magnitude, dist)
        if mmi < min_mmi:
            continue
        impacted.append({
            **a,
            "distance_km": round(dist, 1),
            "mmi": round(mmi, 1),
            "damage_state": damage_state(mmi),
        })
    impacted.sort(key=lambda a: (-a["mmi"], -a["criticality"]))
    rings = []
    for level in (9, 8, 7, 6):
        r = radius_for_mmi(magnitude, level)
        if r > 0:
            rings.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [circle_polygon(lon, lat, r)]},
                "properties": {"mmi": level, "radius_km": r, "damage_state": damage_state(level)},
            })
    return {
        "hazard": "earthquake",
        "epicenter": {"lon": lon, "lat": lat, "magnitude": magnitude},
        "model": "Atkinson & Wald (2007) IPE with Wells & Coppersmith (1994) rupture-length correction — screening estimate, not a ShakeMap",
        "rupture_length_km": round(rupture_length_km(magnitude), 1),
        "summary": _summarise(impacted, "damage_state"),
        "assets": impacted,
        "intensity_rings": {"type": "FeatureCollection", "features": rings},
    }


def fire_exposure(assets: list[dict], fires: list[dict], buffer_km: float = 10.0) -> dict:
    """Assets within ``buffer_km`` of any active-fire detection."""
    pts = [f["geometry"]["coordinates"][:2] for f in fires]
    impacted = []
    for a in assets:
        nearest = min((haversine_km(a["lon"], a["lat"], x, y) for x, y in pts), default=None)
        if nearest is None or nearest > buffer_km:
            continue
        count = sum(1 for x, y in pts if haversine_km(a["lon"], a["lat"], x, y) <= buffer_km)
        level = "high" if nearest <= buffer_km / 3 else "elevated"
        impacted.append({
            **a,
            "nearest_fire_km": round(nearest, 2),
            "detections_in_buffer": count,
            "exposure": level,
        })
    impacted.sort(key=lambda a: (a["nearest_fire_km"], -a["criticality"]))
    return {
        "hazard": "wildfire",
        "buffer_km": buffer_km,
        "detections": len(pts),
        "summary": _summarise(impacted, "exposure"),
        "assets": impacted,
    }


def flood_exposure(assets: list[dict], zones: list[dict]) -> dict:
    impacted = []
    for a in assets:
        for z in zones:
            if point_in_geometry(a["lon"], a["lat"], z["geometry"]):
                impacted.append({
                    **a,
                    "zone_id": z["properties"].get("id"),
                    "zone_name": z["properties"].get("name"),
                    "exposure": z["properties"].get("level", "unknown"),
                })
                break
    return {
        "hazard": "flood",
        "zones": len(zones),
        "summary": _summarise(impacted, "exposure"),
        "assets": impacted,
    }
