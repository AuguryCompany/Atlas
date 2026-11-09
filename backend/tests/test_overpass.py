import pytest

from atlas.connectors import overpass

ELEMENTS = [
    {"type": "node", "id": 1, "lat": 41.27, "lon": 28.75,
     "tags": {"aeroway": "aerodrome", "iata": "IST", "name": "İstanbul Havalimanı", "aerodrome:type": "international"}},
    {"type": "way", "id": 2, "center": {"lat": 39.9, "lon": 32.75},
     "tags": {"amenity": "hospital", "name": "Şehir Hastanesi", "beds": "3700"}},
    {"type": "way", "id": 3, "center": {"lat": 37.48, "lon": 38.32},
     "tags": {"power": "plant", "name": "Atatürk HES", "plant:output:electricity": "2400 MW"}},
    {"type": "way", "id": 4, "center": {"lat": 38.0, "lon": 30.0},
     "tags": {"power": "plant", "name": "Küçük GES", "plant:output:electricity": "5 MW"}},
    {"type": "node", "id": 5, "lat": 40.0, "lon": 33.0,
     "tags": {"power": "substation", "voltage": "380000;154000"}},
    {"type": "node", "id": 6, "lat": 40.0, "lon": 33.0, "tags": {"amenity": "hospital"}},  # unnamed
    {"type": "relation", "id": 7, "tags": {"amenity": "hospital", "name": "No geometry"}},
]

CATS = ["airport", "hospital", "power_plant", "substation"]


def test_to_features_maps_types_and_criticality():
    feats = {f["properties"]["id"]: f["properties"] for f in overpass.to_features(ELEMENTS, CATS)}
    assert set(feats) == {"osm-n1", "osm-w2", "osm-w3", "osm-n5"}
    assert feats["osm-n1"]["type"] == "airport" and feats["osm-n1"]["criticality"] == 5
    assert feats["osm-w2"]["criticality"] == 5 and feats["osm-w2"]["capacity"] == "3700 beds"
    assert feats["osm-w3"]["type"] == "power_plant" and feats["osm-w3"]["criticality"] == 5
    assert feats["osm-n5"]["type"] == "substation" and feats["osm-n5"]["capacity"] == "380 kV"
    assert all(p["source"] == "OpenStreetMap" for p in feats.values())


def test_to_features_respects_requested_categories():
    feats = overpass.to_features(ELEMENTS, ["hospital"])
    assert [f["properties"]["id"] for f in feats] == ["osm-w2"]


def test_build_query_country_and_bbox():
    q = overpass.build_query(["airport"], None, "TR")
    assert 'area["ISO3166-1"="TR"]' in q and 'nwr["aeroway"="aerodrome"]["iata"](area.aoi);' in q
    assert q.strip().endswith("out center tags;")
    qb = overpass.build_query(["hospital"], (26.0, 36.0, 45.0, 42.0))
    assert 'nwr["amenity"="hospital"](36.0,26.0,42.0,45.0);' in qb
    with pytest.raises(ValueError):
        overpass.build_query(["airport"], None, 'TR"];out;')


def test_imported_features_are_valid_inventory_rows(tmp_path):
    from atlas.db import Database
    db = Database(tmp_path / "x.db")
    assert db.upsert_features(overpass.to_features(ELEMENTS, CATS)) == 4
    assert db.get_asset("osm-n1")["extra"]["osm"] == "node/1"
