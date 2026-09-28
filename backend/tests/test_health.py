from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.routes import health as health_module
from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "enterprise-agent-runtime-platform"


def test_health_when_dependencies_are_available(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "database_ping", AsyncMock(return_value=True))
    monkeypatch.setattr(health_module, "redis_ping", AsyncMock(return_value=True))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "ok"
    assert response.json()["redis"] == "ok"


def test_health_is_degraded_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(health_module, "database_ping", AsyncMock(return_value=False))
    monkeypatch.setattr(health_module, "redis_ping", AsyncMock(return_value=True))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "unavailable"
