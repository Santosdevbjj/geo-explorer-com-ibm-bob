"""Fixtures compartilhadas para os testes do Sentinel."""

from __future__ import annotations

import pytest

# ── Eventos válidos ────────────────────────────────────────────────────────


def make_auth_event(
    event_id: str = "evt-001",
    source_ip: str = "192.168.1.10",
    status: str = "failure",
    user_id: str | None = "user_42",
) -> dict:
    """Retorna um dicionário representando um auth_attempt válido."""
    return {
        "event_id": event_id,
        "timestamp": "2025-01-15T14:23:00Z",
        "source_ip": source_ip,
        "dest_ip": "10.0.0.1",
        "dest_port": 443,
        "protocol": "HTTPS",
        "event_type": "auth_attempt",
        "status": status,
        "user_id": user_id,
        "payload_size_bytes": 512,
        "metadata": {},
    }


def make_http_event(
    event_id: str = "evt-002",
    request_path: str = "/api/v1/login",
    status: str = "success",
) -> dict:
    """Retorna um dicionário representando um http_request válido."""
    return {
        "event_id": event_id,
        "timestamp": "2025-01-15T14:24:00Z",
        "source_ip": "192.168.1.20",
        "event_type": "http_request",
        "status": status,
        "request_path": request_path,
        "user_agent": "Mozilla/5.0",
        "payload_size_bytes": 1024,
        "metadata": {},
    }


# ── Fixtures pytest ────────────────────────────────────────────────────────


@pytest.fixture
def valid_auth_event() -> dict:
    return make_auth_event()


@pytest.fixture
def valid_http_event() -> dict:
    return make_http_event()


@pytest.fixture
def valid_batch() -> list[dict]:
    """Batch com 3 eventos válidos e sem duplicatas."""
    return [
        make_auth_event(event_id="evt-001", status="failure"),
        make_auth_event(event_id="evt-002", status="success"),
        make_http_event(event_id="evt-003"),
    ]


@pytest.fixture
def batch_with_duplicate() -> list[dict]:
    """Batch com event_id duplicado."""
    return [
        make_auth_event(event_id="evt-dup"),
        make_auth_event(event_id="evt-dup"),  # duplicata
        make_http_event(event_id="evt-003"),
    ]


@pytest.fixture
def batch_with_invalid() -> list[dict]:
    """Batch com um registro sem campos obrigatórios."""
    return [
        make_auth_event(event_id="evt-001"),
        {"event_id": "evt-bad"},  # falta timestamp, source_ip, event_type, status
        make_http_event(event_id="evt-003"),
    ]


@pytest.fixture
def batch_without_timezone() -> list[dict]:
    """Batch com timestamp sem timezone (deve falhar validação)."""
    event = make_auth_event(event_id="evt-notz")
    event["timestamp"] = "2025-01-15T14:23:00"  # sem 'Z' nem offset
    return [event]
