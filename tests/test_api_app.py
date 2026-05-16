from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_assets_endpoint_returns_list() -> None:
    client = TestClient(app)
    response = client.get("/assets")

    assert response.status_code == 200
    assert isinstance(response.json()["assets"], list)
