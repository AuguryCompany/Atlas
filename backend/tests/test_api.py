def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["product"] == "Augury Atlas"


def test_inventory_starts_empty(empty_client):
    assert empty_client.get("/api/infrastructure").json()["features"] == []
    assert empty_client.get("/api/hazards/floods").json()["features"] == []


def test_infrastructure_filtered(client):
    fc = client.get("/api/infrastructure").json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) > 20
    airports = client.get("/api/infrastructure", params={"types": "airport"}).json()
    assert {f["properties"]["type"] for f in airports["features"]} == {"airport"}
    one = client.get("/api/infrastructure/AP-IST").json()
    assert one["properties"]["name"] == "Istanbul Airport"
    assert client.get("/api/infrastructure/nope").status_code == 404


def test_import_and_delete_asset(client):
    payload = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "geometry": {"type": "Point", "coordinates": [32.0, 39.0]},
        "properties": {"id": "T-1", "name": "Test Substation", "type": "power_plant", "criticality": 2, "owner": "X"},
    }]}
    assert client.post("/api/infrastructure/import", json=payload).json() == {"imported": 1}
    got = client.get("/api/infrastructure/T-1").json()
    assert got["properties"]["extra"] == {"owner": "X"}
    assert client.delete("/api/infrastructure/T-1").status_code == 200
    bad = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [500, 0]}, "properties": {"id": "x", "name": "y"}}]}
    assert client.post("/api/infrastructure/import", json=bad).status_code == 422


def test_hazard_layers_offline(client):
    eq = client.get("/api/hazards/earthquakes", params={"start": "1990-01-01", "min_mag": 6}).json()
    assert eq["metadata"]["source"] == "catalogue" and eq["features"]
    assert client.get("/api/hazards/earthquakes/historical").json()["features"]
    # No synthetic fire data: without FIRMS the layer is empty and says why.
    fires = client.get("/api/hazards/fires").json()
    assert fires["metadata"]["source"] == "unavailable" and fires["features"] == []
    assert client.get("/api/hazards/floods").json()["features"]
    tl = client.get("/api/hazards/earthquakes/timeline", params={"start": "1990-01-01", "bucket": "year"}).json()
    assert any(s["period"] == "2023" and s["count"] >= 2 for s in tl["series"])
    assert client.get("/api/hazards/earthquakes", params={"bbox": "1,2,3"}).status_code == 422


def test_analysis_endpoints(client):
    r = client.post("/api/analysis/earthquake", json={"lon": 37.014, "lat": 37.226, "magnitude": 7.8})
    body = r.json()
    assert r.status_code == 200 and body["summary"]["assets_affected"] > 0
    wf = client.get("/api/analysis/wildfire").json()
    assert wf["hazard"] == "wildfire" and wf["source"] == "unavailable" and wf["assets"] == []
    assert client.get("/api/analysis/flood").json()["hazard"] == "flood"
    grid = client.get("/api/analysis/risk-grid", params={"cell_deg": 1}).json()
    assert grid["features"] and grid["metadata"]["top_cells"][0]["score"] > 0
    assert client.get("/api/analysis/risk-grid", params={"cell_deg": 0.1, "bbox": "-180,-90,180,90"}).status_code == 422


def test_logistics_endpoints(client):
    r = client.get("/api/logistics/nearest", params={"lon": 37.0, "lat": 37.2, "types": "hospital", "k": 3, "with_routes": True}).json()
    assert len(r["results"]) == 3 and r["results"][0]["route"]["source"] == "estimate"
    route = client.get("/api/logistics/route", params={"from": "28.97,41.0", "to": "32.85,39.92"}).json()
    assert route["distance_km"] > 300
    cov = client.get("/api/logistics/coverage", params={"radius_km": 150}).json()
    assert cov["demand_points"] > 0 and 0 <= cov["coverage_ratio"] <= 1


def test_imagery_catalogue(client):
    cat = client.get("/api/imagery").json()
    assert any(b["kind"] == "satellite" for b in cat["basemaps"])
    years = [t["year"] for t in cat["temporal"]]
    assert years == sorted(years) and len(years) >= 5


def test_audit_trail_records_requests(client):
    client.get("/api/infrastructure")
    entries = client.get("/api/audit").json()
    assert any(e["path"] == "/api/infrastructure" and e["status"] == 200 for e in entries)


def test_roles_enforced(auth_client):
    c = auth_client
    assert c.get("/api/infrastructure").status_code == 401
    view = {"X-API-Key": "view-key"}
    assert c.get("/api/infrastructure", headers=view).status_code == 200
    assert c.get("/api/analysis/flood", headers=view).status_code == 403
    assert c.get("/api/analysis/flood", headers={"X-API-Key": "analyst-key"}).status_code == 200
    assert c.get("/api/audit", headers={"X-API-Key": "analyst-key"}).status_code == 403
    entries = c.get("/api/audit", headers={"X-API-Key": "admin-key"}).json()
    assert any(e["status"] == 401 and e["role"] == "none" for e in entries)
    assert any(e["status"] == 403 and e["role"] == "viewer" for e in entries)


def test_flood_exposure_finds_assets_in_reference_zones(client):
    body = client.get("/api/analysis/flood").json()
    names = {a["name"] for a in body["assets"]}
    assert "Adana City Hospital" in names


def test_flood_zone_import_validation_and_delete(client):
    bad = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [30, 40]}, "properties": {"id": "z"}}]}
    assert client.post("/api/hazards/floods/import", json=bad).status_code == 422
    bad_level = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[30, 40], [31, 40], [31, 41], [30, 40]]]}, "properties": {"id": "z", "level": "extreme"}}]}
    assert client.post("/api/hazards/floods/import", json=bad_level).status_code == 422
    assert client.delete("/api/hazards/floods/FZ-CUK").status_code == 200
    assert client.delete("/api/hazards/floods/FZ-CUK").status_code == 404


def test_osm_import_offline_returns_502(client):
    r = client.post("/api/infrastructure/import/osm", json={"categories": ["airport"]})
    assert r.status_code == 502 and "offline" in r.json()["detail"]
    assert client.get("/api/infrastructure/osm/categories").json()["airport"] == "Airport"
