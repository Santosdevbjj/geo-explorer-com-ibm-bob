"""Testes focados em controles de segurança observáveis da API."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from api.index import app
from sentinel.config import settings

client = TestClient(app)


def _event(metadata: dict | None = None) -> dict:
    return {
        "event_id": "security-test",
        "timestamp": "2026-06-01T12:00:00Z",
        "source_ip": "192.0.2.10",
        "event_type": "http_request",
        "status": "success",
        "request_path": "/health",
        "metadata": metadata or {},
    }


def test_placeholder_api_secret_is_rejected_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sentinel_env", "production")
    monkeypatch.setattr(settings, "api_secret_key", "change-me-in-production")
    response = client.post("/analyze", json=_event())
    assert response.status_code == 503


def test_wrong_api_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "sentinel_env", "development")
    monkeypatch.setattr(settings, "api_secret_key", "expected-test-secret")
    response = client.post("/analyze", json=_event(), headers={"X-Api-Key": "wrong"})
    assert response.status_code == 401


def test_oversized_event_is_rejected_without_echoing_payload() -> None:
    response = client.post("/analyze", json=_event({"blob": "x" * 70_000}))
    assert response.status_code == 413
    assert "xxxx" not in response.text


def test_batch_limit_rejects_before_detection(monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_batch_size", 1)
    response = client.post("/analyze/batch", json={"events": [_event(), _event()]})
    assert response.status_code == 422


def test_model_info_does_not_expose_model_filesystem_path() -> None:
    response = client.get("/model-info")
    assert response.status_code == 200
    body = response.json()
    assert "model_loaded" in body
    assert "model_path" not in body
    assert "artifact_path" not in body
