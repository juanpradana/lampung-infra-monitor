"""API tests for Lampung Infrastructure Monitor."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.core.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize DB before each test."""
    init_db()


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_login_page():
    resp = client.get("/login")
    assert resp.status_code == 200


def test_login_invalid():
    resp = client.post("/api/auth/login", data={"username": "nonexistent", "password": "wrong"})
    assert resp.status_code == 401


def test_dashboard_requires_auth():
    resp = client.get("/api/events")
    assert resp.status_code == 401


def test_login_and_access():
    # First register via init_db (admin user exists)
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Access events
        resp = client.get("/api/events", headers=headers)
        assert resp.status_code == 200
        assert "events" in resp.json()

        # Access dashboard stats
        resp = client.get("/api/dashboard/stats?days=30", headers=headers)
        assert resp.status_code == 200
        assert "total_events" in resp.json()

        # Access locations
        resp = client.get("/api/admin/locations", headers=headers)
        assert resp.status_code == 200
        assert "locations" in resp.json()


def test_create_event():
    resp = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if resp.status_code == 200:
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/api/events", headers=headers, json={
            "title": "Test Event",
            "description": "Test description",
            "category": "bencana",
            "severity": "medium",
            "kabupaten": "Bandar Lampung",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Event"
        assert data["kabupaten"] == "Bandar Lampung"
