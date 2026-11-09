import math

import pytest

from atlas import geo


def test_haversine_known_distance():
    # Istanbul (Sultanahmet) -> Ankara (Kızılay) is roughly 350 km great-circle.
    d = geo.haversine_km(28.9784, 41.0082, 32.8541, 39.9208)
    assert 345 < d < 355


def test_destination_roundtrip():
    lon, lat = geo.destination(32.85, 39.92, 90, 100)
    assert math.isclose(geo.haversine_km(32.85, 39.92, lon, lat), 100, rel_tol=1e-6)


def test_circle_polygon_closed_and_radius():
    ring = geo.circle_polygon(30, 40, 50, steps=16)
    assert ring[0] == ring[-1]
    for lon, lat in ring:
        assert math.isclose(geo.haversine_km(30, 40, lon, lat), 50, rel_tol=1e-6)


def test_point_in_polygon_with_hole():
    outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hole = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    poly = [outer, hole]
    assert geo.point_in_polygon(1, 1, poly)
    assert not geo.point_in_polygon(5, 5, poly)
    assert not geo.point_in_polygon(11, 5, poly)
    assert geo.point_in_geometry(1, 1, {"type": "MultiPolygon", "coordinates": [poly]})


@pytest.mark.parametrize("raw", ["1,2,3", "10,0,5,5", "0,0,200,5", "a,b,c,d"])
def test_parse_bbox_rejects_bad_input(raw):
    with pytest.raises(ValueError):
        geo.parse_bbox(raw)


def test_parse_bbox_ok():
    assert geo.parse_bbox("26,36,45,42") == (26, 36, 45, 42)
    assert geo.parse_bbox(None) is None
