"""Sprint UX-01-06 smoke tests for seed endpoints.

Asserts the endpoints exist, require the X-MFM-Drive-Token header (regression
gate against the Fastly-strips-X-Google-* class of bug), and reject missing
seed files cleanly.
"""
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-test@example.com"}


def test_helloworld_seed_requires_drive_token():
    resp = client.post("/api/seed/helloworld", headers=AUTH)
    assert resp.status_code == 400
    assert "X-MFM-Drive-Token" in resp.json()["detail"]


def test_campus_adele_seed_requires_drive_token():
    resp = client.post("/api/seed/campus-adele", headers=AUTH)
    assert resp.status_code == 400
    assert "X-MFM-Drive-Token" in resp.json()["detail"]


def test_seed_endpoints_require_auth():
    """Auth is enforced before drive-token check (and before any Firestore work)."""
    assert client.post("/api/seed/helloworld").status_code == 401
    assert client.post("/api/seed/campus-adele").status_code == 401
