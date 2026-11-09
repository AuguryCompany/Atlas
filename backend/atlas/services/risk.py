"""Regional multi-hazard risk grid.

Risk = Hazard x (0.25 + 0.75 x Exposure), each component normalised to 0..1.

* Seismic hazard: strongest estimated intensity any catalogued event produced
  at the cell centre, mapped from MMI 5..10 to 0..1.
* Wildfire hazard: detection density within 25 km, log-scaled.
* Flood hazard: fraction of a 3x3 sample lattice inside a flood-prone zone,
  weighted by zone level.
* Exposure: sum of asset criticality inside the cell, log-scaled.

It is a transparent screening index for prioritisation, not a probabilistic
hazard assessment, and the weights are exposed in the response.
"""

from __future__ import annotations

import math

from ..geo import BBox, haversine_km, point_in_geometry
from .hazards import estimate_mmi

DEFAULT_WEIGHTS = {"seismic": 0.5, "wildfire": 0.2, "flood": 0.3}
FLOOD_LEVEL = {"high": 1.0, "medium": 0.6, "low": 0.3}


def _log_norm(value: float, cap: float) -> float:
    return min(1.0, math.log1p(value) / math.log1p(cap)) if value > 0 else 0.0


def risk_class(score: float) -> str:
    if score >= 60:
        return "very_high"
    if score >= 40:
        return "high"
    if score >= 20:
        return "medium"
    if score >= 5:
        return "low"
    return "minimal"


def compute_grid(
    bbox: BBox,
    cell_deg: float,
    assets: list[dict],
    earthquakes: list[dict],
    fires: list[dict],
    flood_zones: list[dict],
    weights: dict[str, float] | None = None,
) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_w = sum(weights.values()) or 1.0
    west, south, east, north = bbox
    cols = max(1, math.ceil((east - west) / cell_deg))
    rows = max(1, math.ceil((north - south) / cell_deg))
    if cols * rows > 5000:
        raise ValueError("grid too fine for this extent (max 5000 cells)")

    quakes = [
        (f["geometry"]["coordinates"][0], f["geometry"]["coordinates"][1], f["properties"]["mag"])
        for f in earthquakes if f["properties"].get("mag") is not None
    ]
    fire_pts = [f["geometry"]["coordinates"][:2] for f in fires]

    features = []
    for r in range(rows):
        for c in range(cols):
            w0, s0 = west + c * cell_deg, south + r * cell_deg
            e0, n0 = min(w0 + cell_deg, east), min(s0 + cell_deg, north)
            cx, cy = (w0 + e0) / 2, (s0 + n0) / 2

            max_mmi = max(
                (estimate_mmi(m, haversine_km(cx, cy, x, y)) for x, y, m in quakes), default=0.0
            )
            seismic = min(1.0, max(0.0, (max_mmi - 5.0) / 5.0))

            fire_n = sum(1 for x, y in fire_pts if haversine_km(cx, cy, x, y) <= 25.0)
            wildfire = _log_norm(fire_n, 30)

            flood = 0.0
            for z in flood_zones:
                lvl = FLOOD_LEVEL.get(z["properties"].get("level", "low"), 0.3)
                hits = sum(
                    point_in_geometry(w0 + (e0 - w0) * i / 4, s0 + (n0 - s0) * j / 4, z["geometry"])
                    for i in (1, 2, 3) for j in (1, 2, 3)
                )
                flood = max(flood, lvl * hits / 9)

            in_cell = [a for a in assets if w0 <= a["lon"] < e0 and s0 <= a["lat"] < n0]
            exposure = _log_norm(sum(a["criticality"] for a in in_cell), 25)

            hazard = (
                weights["seismic"] * seismic
                + weights["wildfire"] * wildfire
                + weights["flood"] * flood
            ) / total_w
            score = round(100 * hazard * (0.25 + 0.75 * exposure), 1)
            features.append({
                "type": "Feature",
                "id": f"{r}-{c}",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[w0, s0], [e0, s0], [e0, n0], [w0, n0], [w0, s0]]],
                },
                "properties": {
                    "cell": f"{r}-{c}",
                    "score": score,
                    "class": risk_class(score),
                    "seismic": round(seismic, 3),
                    "wildfire": round(wildfire, 3),
                    "flood": round(flood, 3),
                    "exposure": round(exposure, 3),
                    "assets": len(in_cell),
                },
            })
    ranked = sorted(features, key=lambda f: -f["properties"]["score"])
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "cell_deg": cell_deg,
            "weights": weights,
            "formula": "score = 100 * hazard * (0.25 + 0.75 * exposure)",
            "top_cells": [f["properties"] for f in ranked[:10]],
        },
    }
