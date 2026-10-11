"""Testes de integração — api/index.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)


# ── Fixtures de payload ────────────────────────────────────────────────────


def _valid_event(event_id: str = "evt-001", status: str = "failure") -> dict:
    return {
        "event_id": event_id,
        "timestamp": "2025-01-15T14:23:00Z",
        "source_ip": "192.168.1.10",
        "dest_ip": "10.0.0.1",
        "dest_port": 443,
        "protocol": "HTTPS",
        "event_type": "auth_attempt",
        "status": status,
        "payload_size_bytes": 512,
        "metadata": {},
    }


def _brute_force_batch(n: int = 10, ip: str = "10.10.10.10") -> list[dict]:
    """Gera rajada de auth failures para disparar BruteForceRule."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone.utc)
    return [
        {
            "event_id": f"bf-{i:03d}",
            "timestamp": (base + timedelta(seconds=i * 10)).isoformat(),
            "source_ip": ip,
            "event_type": "auth_attempt",
            "status": "failure",
            "payload_size_bytes": 256,
            "metadata": {},
        }
        for i in range(n)
    ]


# ── /health ────────────────────────────────────────────────────────────────


class TestHealth:
    def test_returns_200(self) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_status_ok(self) -> None:
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_service_name(self) -> None:
        resp = client.get("/health")
        assert resp.json()["service"] == "sentinel"


# ── /ingest ────────────────────────────────────────────────────────────────


class TestIngest:
    def test_valid_batch_returns_200(self) -> None:
        payload = {"events": [_valid_event()]}
        resp = client.post("/ingest", json=payload)
        assert resp.status_code == 200

    def test_valid_batch_passes(self) -> None:
        payload = {"events": [_valid_event("e1"), _valid_event("e2", "success")]}
        resp = client.post("/ingest", json=payload)
        assert resp.json()["passed"] is True

    def test_empty_events_rejected(self) -> None:
        resp = client.post("/ingest", json={"events": []})
        assert resp.status_code == 422

    def test_invalid_schema_reports_errors(self) -> None:
        bad_event = {"event_id": "bad"}  # falta timestamp, source_ip, etc.
        resp = client.post("/ingest", json={"events": [bad_event]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["invalid_records"] >= 1
        assert body["passed"] is False

    def test_duplicate_ids_detected(self) -> None:
        dup = _valid_event("dup-id")
        resp = client.post("/ingest", json={"events": [dup, dup]})
        body = resp.json()
        assert "dup-id" in body["duplicate_ids"]
        assert body["passed"] is False

    def test_invalid_ip_reported(self) -> None:
        evt = _valid_event("bad-ip")
        evt["source_ip"] = "999.999.999.999"
        resp = client.post("/ingest", json={"events": [evt]})
        assert resp.json()["invalid_records"] >= 1


# ── /detect ────────────────────────────────────────────────────────────────


class TestDetect:
    def test_valid_events_return_200(self) -> None:
        payload = {"events": [_valid_event("d1"), _valid_event("d2", "success")]}
        resp = client.post("/detect", json=payload)
        assert resp.status_code == 200

    def test_response_has_required_fields(self) -> None:
        payload = {"events": [_valid_event()]}
        resp = client.post("/detect", json=payload)
        body = resp.json()
        assert "alerts_generated" in body
        assert "alerts" in body

    def test_brute_force_generates_alert(self) -> None:
        """10 falhas de auth do mesmo IP em 300s devem gerar alerta."""
        batch = _brute_force_batch(n=10)
        resp = client.post("/detect", json={"events": batch})
        body = resp.json()
        assert body["alerts_generated"] >= 1

    def test_alert_has_signals(self) -> None:
        batch = _brute_force_batch(n=10)
        resp = client.post("/detect", json={"events": batch})
        alerts = resp.json()["alerts"]
        if alerts:
            assert len(alerts[0]["signals"]) >= 1

    def test_alert_has_limitations(self) -> None:
        batch = _brute_force_batch(n=10)
        resp = client.post("/detect", json={"events": batch})
        alerts = resp.json()["alerts"]
        if alerts:
            assert alerts[0]["limitations"]

    def test_alert_score_not_exceeds_one(self) -> None:
        batch = _brute_force_batch(n=20)
        resp = client.post("/detect", json={"events": batch})
        for alert in resp.json()["alerts"]:
            assert 0.0 <= alert["score"] <= 1.0

    def test_invalid_batch_with_validate_returns_422(self) -> None:
        bad_event = {"event_id": "bad-detect"}
        resp = client.post("/detect", json={"events": [bad_event], "validate_first": True})
        assert resp.status_code == 422

    def test_empty_events_rejected(self) -> None:
        resp = client.post("/detect", json={"events": []})
        assert resp.status_code == 422


# ── /alerts ────────────────────────────────────────────────────────────────


class TestAlerts:
    def test_list_alerts_returns_list(self) -> None:
        resp = client.get("/alerts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_nonexistent_alert_returns_404(self) -> None:
        resp = client.get("/alerts/nonexistent-id-xyz")
        assert resp.status_code == 404

    def test_generated_alert_is_retrievable(self) -> None:
        """Alerta gerado por /detect deve ser recuperável por /alerts/{id}."""
        batch = _brute_force_batch(n=10)
        detect_resp = client.post("/detect", json={"events": batch})
        alerts = detect_resp.json()["alerts"]
        if not alerts:
            pytest.skip("Nenhum alerta gerado — ajuste o limiar no .env")
        alert_id = alerts[0]["alert_id"]
        get_resp = client.get(f"/alerts/{alert_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["alert_id"] == alert_id


# ── Endpoints do contrato Sentinel ────────────────────────────────────────


class TestAnalyzeEndpoints:
    def test_model_info_distinguishes_api_from_model(self) -> None:
        response = client.get("/model-info")
        assert response.status_code == 200
        body = response.json()
        assert body["service"] == "sentinel"
        assert body["inference_mode"] in {"rules-only", "rules+model"}
        assert body["score_is_calibrated_probability"] is False

    def test_analyze_single_valid_event(self) -> None:
        response = client.post("/analyze", json=_valid_event("analyze-1", "success"))
        assert response.status_code == 200
        assert "alerts_generated" in response.json()

    def test_analyze_batch_valid_events(self) -> None:
        response = client.post(
            "/analyze/batch",
            json={"events": [_valid_event("batch-1", "success"), _valid_event("batch-2", "failure")]},
        )
        assert response.status_code == 200
        assert "alerts_generated" in response.json()

    def test_analyze_rejects_invalid_event_schema(self) -> None:
        response = client.post("/analyze", json={"event_id": "bad"})
        assert response.status_code == 422

    def test_analyze_batch_rejects_empty_list(self) -> None:
        response = client.post("/analyze/batch", json={"events": []})
        assert response.status_code == 422

    def test_analyze_batch_enforces_maximum(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from sentinel.config import settings

        monkeypatch.setattr(settings, "max_batch_size", 1)
        response = client.post(
            "/analyze/batch",
            json={"events": [_valid_event("max-1", "success"), _valid_event("max-2", "success")]},
        )
        assert response.status_code == 422

    def test_protected_analyze_requires_key_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from sentinel.config import settings

        monkeypatch.setattr(settings, "api_secret_key", "test-only-key")
        response = client.post("/analyze", json=_valid_event("auth-required", "success"))
        assert response.status_code == 401
