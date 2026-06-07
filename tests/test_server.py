"""Unit tests for ChainObserver FastAPI server endpoints."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    from server import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["service"] == "chainobserver"


def test_landing_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ChainObserver" in r.text
    assert "diagnose" in r.text.lower()
    assert "ETHGlobal" in r.text


def test_diagnose_missing_api_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("USE_VERTEX", raising=False)
    r = client.post("/diagnose", json={"tx_hash": "0xabc123"})
    assert r.status_code == 503
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_diagnose_empty_hash(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    r = client.post("/diagnose", json={"tx_hash": ""})
    # Either 422 (validation) or 503 (no key) is acceptable
    assert r.status_code in (422, 503)


def test_docs_endpoint(client):
    r = client.get("/docs")
    assert r.status_code == 200


def test_openapi_schema(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert "ChainObserver" in schema["info"]["title"]
    assert "/diagnose" in schema["paths"]
    assert "/health" in schema["paths"]
