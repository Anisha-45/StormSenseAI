"""HTTP-level tests using FastAPI's TestClient. They are skipped automatically when fastapi/httpx are not
installed. Run `pip install -r requirements.txt` first, then `pytest`."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from app.db import database as db  # noqa: E402


@pytest.fixture()
def client(tmp_app):
    from app.main import app
    db.init_db()
    with TestClient(app) as c:
        yield c


def _register(client, email="user@example.com", role="citizen"):
    r = client.post("/api/v1/auth/register", json={"email": email, "name": "Test User", "password": "Storm1234", "role": role})
    assert r.status_code == 201, r.text
    t = client.post("/api/v1/auth/login", json={"email": email, "password": "Storm1234"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _promote(email, role):
    with db.session() as con:
        con.execute("UPDATE users SET role=? WHERE email=?", (role, email))


def test_health(client):
    assert client.get("/api/v1/health").status_code == 200


def test_auth_required_and_profile(client):
    assert client.get("/api/v1/auth/profile").status_code == 401
    h = _register(client)
    assert client.get("/api/v1/auth/profile", headers=h).json()["role"] == "citizen"


def test_cannot_register_as_admin(client):
    r = client.post("/api/v1/auth/register", json={"email": "x@y.co", "name": "Eve", "password": "Storm1234", "role": "administrator"})
    assert r.status_code == 422 or r.status_code == 403


def test_bad_login(client):
    assert client.post("/api/v1/auth/login", json={"email": "no@x.co", "password": "Storm1234"}).status_code == 401


def test_citizen_cannot_use_staff_endpoints(client):
    h = _register(client)
    for method, url in (("get", "/api/v1/resources"), ("get", "/api/v1/coordination/overview"), ("get", "/api/v1/admin/users"),
                        ("post", "/api/v1/clustering/dbscan")):
        r = getattr(client, method)(url, headers=h, **({"json": {}} if method == "post" else {}))
        assert r.status_code == 403, url


def test_incident_privacy_and_review(client):
    a = _register(client, "a@x.co")
    b = _register(client, "b@x.co")
    c = _register(client, "c@x.co")
    _promote("c@x.co", "coordinator")
    r = client.post("/api/v1/incidents", headers=a, data={"category": "flooded_road", "description": "Water over the road by the bridge"})
    assert r.status_code == 201 and r.json()["verification"] == "unverified"
    assert client.get("/api/v1/incidents", headers=b).json() == []
    assert len(client.get("/api/v1/incidents", headers=c).json()) == 1
    iid = r.json()["id"]
    assert client.patch(f"/api/v1/incidents/{iid}/status", headers=a, json={"verification": "verified"}).status_code == 403
    assert client.patch(f"/api/v1/incidents/{iid}/status", headers=c, json={"verification": "verified"}).json()["verification"] == "verified"


def test_upload_requires_permission_and_validates(client):
    citizen = _register(client, "a@x.co")
    files = {"file": ("d.csv", b"a,b\n1,2\n", "text/csv")}
    assert client.post("/api/v1/datasets/upload", headers=citizen, files=files).status_code == 403
    researcher = _register(client, "r@x.co", role="researcher")
    ok = client.post("/api/v1/datasets/upload", headers=researcher, files=files)
    assert ok.status_code == 201
    bad = client.post("/api/v1/datasets/upload", headers=researcher, files={"file": ("d.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 400


def test_analytics_endpoints_with_processed_data(client):
    r = client.get("/api/v1/overview")
    if r.status_code == 503:
        pytest.skip("dataset not processed")
    assert r.json()["total_unique_events"] > 0
    assert client.get("/api/v1/temporal/yearly").status_code == 200
    assert client.get("/api/v1/events/search?state=Texas&page_size=3").json()["rows"]
    assert client.get("/api/v1/events/-5").status_code == 404


def test_clustering_endpoints(client):
    h = _register(client, "r@x.co", role="researcher")
    r = client.post("/api/v1/clustering/hierarchical", headers=h, json={"n_clusters": 4, "feature_config": {"sample_size": 400}})
    if r.status_code == 503:
        pytest.skip("dataset not processed")
    assert r.status_code == 200 and r.json()["metrics"]["n_clusters"] == 4
    eid = r.json()["experiment_id"]
    assert client.get(f"/api/v1/clustering/{eid}").json()["algorithm"] == "hierarchical"
    d = client.post("/api/v1/clustering/dbscan", headers=h, json={"min_samples": 8, "feature_config": {"sample_size": 400}})
    assert d.status_code == 200
    assert client.get(f"/api/v1/clustering/compare?ids={eid},{d.json()['experiment_id']}").status_code == 200
    assert client.post("/api/v1/clustering/dbscan", headers=h, json={"eps": -1}).status_code == 422


def test_assistant(client):
    r = client.post("/api/v1/assistant/query", json={"question": "Which states have the most flood events?"})
    if r.status_code == 503:
        pytest.skip("dataset not processed")
    assert r.json()["source"]
