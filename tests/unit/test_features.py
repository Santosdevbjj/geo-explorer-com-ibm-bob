"""Testes unitários — src/sentinel/features/engineering.py"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pandas as pd

from sentinel.features.engineering import (
    FEATURE_COLUMNS,
    _empty_features_df,
    extract_features,
)
from sentinel.schemas import LogEvent

# ── Helpers ────────────────────────────────────────────────────────────────

# EXPECTED_COLUMNS agora referencia o schema canônico exportado pelo módulo,
# para garantir que este teste acompanha futuras expansões automaticamente.
EXPECTED_COLUMNS = set(FEATURE_COLUMNS)


def _ts(offset_seconds: int = 0) -> str:
    base = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _make_event(
    event_id: str,
    ip: str = "10.0.0.1",
    event_type: str = "auth_attempt",
    status: str = "failure",
    offset: int = 0,
    request_path: str | None = None,
    payload_size: int = 512,
) -> LogEvent:
    data: dict = {
        "event_id": event_id,
        "timestamp": _ts(offset),
        "source_ip": ip,
        "event_type": event_type,
        "status": status,
        "payload_size_bytes": payload_size,
        "metadata": {},
    }
    if request_path:
        data["request_path"] = request_path
    return LogEvent.model_validate(data)


# ── Schema do DataFrame ────────────────────────────────────────────────────


class TestDataFrameSchema:
    def test_empty_batch_returns_correct_columns(self) -> None:
        df = extract_features([])
        assert set(df.columns) == EXPECTED_COLUMNS

    def test_empty_batch_has_zero_rows(self) -> None:
        df = extract_features([])
        assert len(df) == 0

    def test_nonempty_batch_returns_correct_columns(self) -> None:
        events = [_make_event("e1"), _make_event("e2", offset=10)]
        df = extract_features(events)
        assert set(df.columns) == EXPECTED_COLUMNS

    def test_empty_features_df_helper(self) -> None:
        df = _empty_features_df()
        assert set(df.columns) == EXPECTED_COLUMNS
        assert len(df) == 0


# ── Cálculo de features ────────────────────────────────────────────────────


class TestFeatureValues:
    def test_auth_failure_rate_all_failures(self) -> None:
        """5 auth failures → auth_failure_rate = 1.0 na primeira janela."""
        events = [
            _make_event(f"e{i}", status="failure", offset=i * 10) for i in range(5)
        ]
        df = extract_features(events, window_seconds=300)
        # Primeira janela do único IP
        row = df.iloc[0]
        assert row["auth_failure_rate"] == 1.0

    def test_auth_failure_rate_mixed(self) -> None:
        """2 failures + 2 successes → auth_failure_rate = 0.5."""
        events = [
            _make_event("e1", status="failure", offset=0),
            _make_event("e2", status="failure", offset=10),
            _make_event("e3", status="success", offset=20),
            _make_event("e4", status="success", offset=30),
        ]
        df = extract_features(events, window_seconds=300)
        row = df.iloc[0]
        assert row["auth_failure_rate"] == 0.5

    def test_request_count_only_http(self) -> None:
        """request_count conta apenas http_request."""
        events = [
            _make_event("e1", event_type="http_request", status="success", offset=0),
            _make_event("e2", event_type="http_request", status="success", offset=10),
            _make_event("e3", event_type="auth_attempt", status="failure", offset=20),
        ]
        df = extract_features(events, window_seconds=300)
        row = df.iloc[0]
        assert row["request_count"] == 2

    def test_unique_paths_counts_distinct(self) -> None:
        events = [
            _make_event(
                "e1",
                event_type="http_request",
                status="success",
                request_path="/a",
                offset=0,
            ),
            _make_event(
                "e2",
                event_type="http_request",
                status="success",
                request_path="/a",
                offset=10,
            ),
            _make_event(
                "e3",
                event_type="http_request",
                status="success",
                request_path="/b",
                offset=20,
            ),
        ]
        df = extract_features(events, window_seconds=300)
        row = df.iloc[0]
        assert row["unique_paths"] == 2

    def test_failure_ratio_includes_blocked(self) -> None:
        """failure_ratio conta failure E blocked."""
        events = [
            _make_event("e1", status="failure", offset=0),
            _make_event("e2", status="blocked", offset=10),
            _make_event("e3", status="success", offset=20),
            _make_event("e4", status="success", offset=30),
        ]
        df = extract_features(events, window_seconds=300)
        row = df.iloc[0]
        assert row["failure_ratio"] == 0.5

    def test_payload_size_mean(self) -> None:
        events = [
            _make_event("e1", payload_size=100, offset=0),
            _make_event("e2", payload_size=300, offset=10),
        ]
        df = extract_features(events, window_seconds=300)
        row = df.iloc[0]
        assert row["payload_size_mean"] == 200.0


# ── Janela deslizante ──────────────────────────────────────────────────────


class TestWindowBehavior:
    def test_events_outside_window_not_counted(self) -> None:
        """Evento além da janela não deve ser contado na janela do anchor."""
        # window=60s; evento em offset=100s está fora da janela do anchor em offset=0
        events = [
            _make_event("e1", status="failure", offset=0),
            _make_event("e2", status="failure", offset=100),
        ]
        df = extract_features(events, window_seconds=60)
        # Primeira janela (anchor=e1): apenas e1 deveria estar dentro
        first_row = df[df["source_ip"] == "10.0.0.1"].iloc[0]
        assert first_row["auth_failure_rate"] == 1.0
        # Contagem de total de eventos na janela do anchor = 1 (não 2)
        assert first_row["failure_ratio"] == 1.0

    def test_multiple_ips_separated(self) -> None:
        """Dois IPs distintos → features calculadas separadamente."""
        events = [
            _make_event("e1", ip="1.1.1.1", status="failure", offset=0),
            _make_event("e2", ip="1.1.1.1", status="failure", offset=10),
            _make_event("e3", ip="2.2.2.2", status="success", offset=0),
            _make_event("e4", ip="2.2.2.2", status="success", offset=10),
        ]
        df = extract_features(events, window_seconds=300)
        ip_values = df.groupby("source_ip")["auth_failure_rate"].max()
        assert ip_values["1.1.1.1"] == 1.0
        assert ip_values["2.2.2.2"] == 0.0

    def test_no_duplicate_rows_for_same_ip_window(self) -> None:
        """Não deve haver linhas duplicadas (source_ip, window_start)."""
        events = [_make_event(f"e{i}", offset=i * 10) for i in range(5)]
        df = extract_features(events, window_seconds=300)
        dupes = df.duplicated(subset=["source_ip", "window_start"])
        assert not dupes.any()


# ── Valores de borda ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_event_produces_one_row(self) -> None:
        df = extract_features([_make_event("e1")])
        assert len(df) == 1

    def test_payload_none_treated_as_zero(self) -> None:
        """payload_size_bytes=None deve ser tratado como 0."""
        event = LogEvent.model_validate(
            {
                "event_id": "e-no-payload",
                "timestamp": _ts(0),
                "source_ip": "10.0.0.1",
                "event_type": "auth_attempt",
                "status": "success",
                "metadata": {},
            }
        )
        df = extract_features([event])
        assert df.iloc[0]["payload_size_mean"] == 0.0

    def test_no_http_events_request_count_zero(self) -> None:
        events = [
            _make_event(f"e{i}", event_type="auth_attempt", offset=i * 10)
            for i in range(3)
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["request_count"] == 0

    def test_all_features_are_numeric(self) -> None:
        events = [_make_event(f"e{i}", offset=i * 10) for i in range(3)]
        df = extract_features(events, window_seconds=300)
        numeric_cols = [
            "auth_failure_rate",
            "request_count",
            "unique_paths",
            "failure_ratio",
            "payload_size_mean",
        ]
        for col in numeric_cols:
            assert pd.api.types.is_numeric_dtype(df[col]), (
                f"Coluna {col} não é numérica"
            )
