"""Testes das ferramentas MCP locais sem exigir o SDK no job unitário."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_PATH = ROOT / "mcp" / "tools.py"
_spec = importlib.util.spec_from_file_location("sentinel_mcp_test_tools", TOOLS_PATH)
assert _spec is not None and _spec.loader is not None
tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tools)


def _valid_event() -> dict[str, Any]:
    return {
        "event_id": "mcp-test-event",
        "timestamp": "2026-01-15T14:23:00Z",
        "source_ip": "192.168.1.10",
        "event_type": "http_request",
        "status": "success",
        "request_path": "/api/v1/health",
        "user_agent": "Mozilla/5.0",
        "metadata": {},
    }


def test_model_info_distinguishes_model_from_service() -> None:
    result = tools.get_model_info()
    assert result["service"] == "sentinel"
    assert result["inference_mode"] == "rules-only"
    assert "model_inference_status" in result
    assert result["score_is_calibrated_probability"] is False


def test_analyze_event_valid_payload_does_not_echo_event() -> None:
    result = tools.analyze_event(_valid_event())
    assert result["valid"] is True
    assert "source_ip" not in result
    assert "event" not in result


def test_analyze_event_invalid_payload_returns_field_errors_not_values() -> None:
    result = tools.analyze_event({"event_id": "secret", "timestamp": "not-a-date"})
    assert result["valid"] is False
    assert result["issues"]
    assert "secret" not in str(result)


def test_analyze_event_rejects_oversized_payload() -> None:
    with pytest.raises(ValueError, match="excede o limite"):
        tools.analyze_event({"payload": "x" * tools.MAX_EVENT_BYTES})


def test_metrics_summary_has_explicit_unavailable_state_or_summary() -> None:
    result = tools.get_metrics_summary()
    assert "available" in result
    if result["available"]:
        assert "summary" in result


def test_drift_summary_has_explicit_interpretation() -> None:
    result = tools.get_drift_summary()
    assert "available" in result
    assert "interpretation" in result or "message" in result
