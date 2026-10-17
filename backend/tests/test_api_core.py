async def test_health_reports_checks(api):
    r = await api.get("/api/health")
    body = r.json()
    assert r.status_code == 200 and body["checks"]["database"] is True and body["checks"]["nvidia_key"] is True


async def test_workspace_roundtrip(api):
    body = {"name": "Acme Robotics", "website": None, "description": "Cobots", "value_props": [], "offering_type": "dealer"}
    assert (await api.put("/api/workspace", json=body)).status_code == 200
    assert (await api.get("/api/workspace")).json()["offering_type"] == "dealer"


async def test_validation_error_shape(api):
    r = await api.put("/api/workspace", json={"name": "x", "offering_type": "b2c"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
