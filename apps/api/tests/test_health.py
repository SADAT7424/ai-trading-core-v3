"""
Foundation-stage tests.

/health must never depend on the database or Redis being up — it only proves
the API process itself is alive. /ready is allowed to report a degraded
dependency without raising, which this test also verifies.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_does_not_require_dependencies() -> None:
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_ready_reports_dependency_status_without_crashing() -> None:
    response = client.get("/api/v1/system/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body["dependencies"]
    assert "redis" in body["dependencies"]
