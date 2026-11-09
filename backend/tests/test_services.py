from atlas.services import hazards, logistics, risk


ASSETS = [
    {"id": "A", "name": "Near", "type": "hospital", "lon": 37.0, "lat": 37.2, "criticality": 5},
    {"id": "B", "name": "Mid", "type": "airport", "lon": 37.5, "lat": 37.0, "criticality": 3},
    {"id": "C", "name": "Far", "type": "port", "lon": 29.0, "lat": 41.0, "criticality": 4},
]


def test_mmi_decreases_with_distance_and_grows_with_magnitude():
    assert hazards.estimate_mmi(7.8, 10) > hazards.estimate_mmi(7.8, 100) > hazards.estimate_mmi(7.8, 400)
    assert hazards.estimate_mmi(7.8, 50) > hazards.estimate_mmi(6.0, 50)
    assert 8.5 < hazards.estimate_mmi(7.8, 10) <= 12


def test_finite_fault_raises_far_field_intensity_for_large_events():
    point = hazards.estimate_mmi(7.8, 100, finite_fault=False)
    finite = hazards.estimate_mmi(7.8, 100)
    assert finite > point + 1
    # Negligible difference for moderate events.
    assert abs(hazards.estimate_mmi(5.0, 100) - hazards.estimate_mmi(5.0, 100, finite_fault=False)) < 0.3


def test_radius_for_mmi_is_consistent():
    r = hazards.radius_for_mmi(7.5, 7.0)
    assert r > 0
    assert abs(hazards.estimate_mmi(7.5, r) - 7.0) < 0.05
    assert hazards.radius_for_mmi(4.0, 9.0) == 0.0


def test_earthquake_impact_ranks_assets():
    out = hazards.earthquake_impact(ASSETS, 37.014, 37.226, 7.8)
    ids = [a["id"] for a in out["assets"]]
    assert ids[0] == "A" and "C" not in ids
    assert out["summary"]["assets_affected"] == len(ids)
    assert out["intensity_rings"]["features"]


def test_fire_and_flood_exposure():
    fires = [{"geometry": {"coordinates": [37.01, 37.21]}}]
    out = hazards.fire_exposure(ASSETS, fires, buffer_km=5)
    assert [a["id"] for a in out["assets"]] == ["A"]
    assert out["assets"][0]["exposure"] == "high"

    zone = {
        "geometry": {"type": "Polygon", "coordinates": [[[28.9, 40.9], [29.1, 40.9], [29.1, 41.1], [28.9, 41.1], [28.9, 40.9]]]},
        "properties": {"id": "Z", "name": "Zone", "level": "high"},
    }
    fl = hazards.flood_exposure(ASSETS, [zone])
    assert [a["id"] for a in fl["assets"]] == ["C"]


def test_risk_grid_scores_hazard_and_exposure():
    quake = {"geometry": {"coordinates": [37.014, 37.226]}, "properties": {"mag": 7.8}}
    grid = risk.compute_grid((36.0, 36.0, 38.0, 38.0), 1.0, ASSETS, [quake], [], [])
    assert len(grid["features"]) == 4
    top = grid["metadata"]["top_cells"][0]
    assert top["score"] > 0 and top["assets"] >= 1
    assert all(0 <= f["properties"]["score"] <= 100 for f in grid["features"])


def test_nearest_and_coverage():
    res = logistics.nearest(ASSETS, 37.0, 37.2, k=2)
    assert [a["id"] for a in res] == ["A", "B"]
    cov = logistics.coverage([ASSETS[0]], ASSETS[1:], 100)
    assert cov["covered"] == 1 and cov["uncovered"][0]["id"] == "C"
