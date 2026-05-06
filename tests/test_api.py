"""Tests for FastAPI endpoints."""

from fastapi.testclient import TestClient

from multi_agent_research_lab.services.api.main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "docs" in data
    assert data["version"] == "0.1.0"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_trace_not_found() -> None:
    response = client.get("/trace/nonexistent")
    assert response.status_code == 200
    assert "error" in response.json()
