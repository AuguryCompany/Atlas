"""Dependency-free geospatial primitives (WGS84 lon/lat, degrees)."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

EARTH_RADIUS_KM = 6371.0088

Coord = Sequence[float]  # (lon, lat)
BBox = tuple[float, float, float, float]  # (west, south, east, north)


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def destination(lon: float, lat: float, bearing_deg: float, distance_km: float) -> tuple[float, float]:
    """Point reached travelling ``distance_km`` from (lon, lat) on ``bearing_deg``."""
    d = distance_km / EARTH_RADIUS_KM
    b = math.radians(bearing_deg)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(
        math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2)
    )
    return ((math.degrees(l2) + 540) % 360 - 180, math.degrees(p2))


def circle_polygon(lon: float, lat: float, radius_km: float, steps: int = 64) -> list[list[float]]:
    """Closed ring approximating a geodesic circle."""
    ring = [list(destination(lon, lat, 360 * i / steps, radius_km)) for i in range(steps)]
    ring.append(ring[0])
    return ring


def point_in_ring(lon: float, lat: float, ring: Sequence[Coord]) -> bool:
    """Ray-casting point-in-polygon test for a single linear ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def point_in_polygon(lon: float, lat: float, polygon: Sequence[Sequence[Coord]]) -> bool:
    """GeoJSON Polygon coordinates: outer ring followed by optional holes."""
    if not polygon or not point_in_ring(lon, lat, polygon[0]):
        return False
    return not any(point_in_ring(lon, lat, hole) for hole in polygon[1:])


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    gtype = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if gtype == "Polygon":
        return point_in_polygon(lon, lat, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon(lon, lat, poly) for poly in coords)
    return False


def in_bbox(lon: float, lat: float, bbox: BBox) -> bool:
    west, south, east, north = bbox
    return west <= lon <= east and south <= lat <= north


def parse_bbox(raw: str | None) -> BBox | None:
    """Parse ``west,south,east,north``; raise ValueError on malformed input."""
    if not raw:
        return None
    parts = [float(p) for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be west,south,east,north")
    west, south, east, north = parts
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("bbox out of range or inverted")
    return (west, south, east, north)


def feature(geometry: dict, properties: dict, feature_id: str | int | None = None) -> dict:
    out: dict = {"type": "Feature", "geometry": geometry, "properties": properties}
    if feature_id is not None:
        out["id"] = feature_id
    return out


def feature_collection(features: Iterable[dict], **meta) -> dict:
    fc: dict = {"type": "FeatureCollection", "features": list(features)}
    if meta:
        fc["metadata"] = meta
    return fc


def point(lon: float, lat: float) -> dict:
    return {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}
