"""Testes unitários para as novas features de engineering.py.

Cobre:
- FEATURE_COLUMNS: schema canônico de saída
- Novas features: auth_failure_count, req_per_second, scan_path_hits,
  error_count, timeout_ratio, payload_size_std, inter_event_mean_ms,
  inter_event_min_ms, scanner_agent_ratio
- Funções de análise exploratória: compute_volume_stats, compute_request_frequency,
  compute_error_rate_by_type, compute_endpoint_diversity, compute_temporal_repetition
- Ausência de target leakage: nenhuma função usa metadata.label
- Determinismo: mesmo input → mesmo output
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sentinel.features.engineering import (
    FEATURE_COLUMNS,
    _compute_inter_event_stats,
    _is_scan_path,
    _is_scanner_agent,
    compute_endpoint_diversity,
    compute_error_rate_by_type,
    compute_request_frequency,
    compute_temporal_repetition,
    compute_volume_stats,
    extract_features,
)
from sentinel.schemas import LogEvent


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ts(offset_seconds: int = 0) -> str:
    base = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _make_event(
    event_id: str = "e1",
    ip: str = "10.0.0.1",
    event_type: str = "auth_attempt",
    status: str = "failure",
    offset: int = 0,
    request_path: str | None = None,
    user_agent: str | None = None,
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
    if request_path is not None:
        data["request_path"] = request_path
    if user_agent is not None:
        data["user_agent"] = user_agent
    return LogEvent.model_validate(data)


def _make_raw_df(n: int = 20, seed: int = 0) -> pd.DataFrame:
    """DataFrame de eventos brutos sem metadata.label para funções de EDA."""
    import random
    rng = random.Random(seed)
    base = datetime(2025, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
    event_types = ["auth_attempt", "http_request", "dns_query", "network_flow"]
    statuses = ["success", "failure", "blocked", "timeout"]
    paths = ["/api/v1/login", "/api/v1/data", "/.env", "/admin", None]
    rows = []
    for i in range(n):
        rows.append({
            "event_id": f"evt-{i:04d}",
            "timestamp": (base + timedelta(seconds=rng.randint(0, 3600))).isoformat(),
            "source_ip": f"10.0.0.{rng.randint(1, 5)}",
            "event_type": rng.choice(event_types),
            "status": rng.choice(statuses),
            "request_path": rng.choice(paths),
            "user_agent": rng.choice([None, "Mozilla/5.0", "sqlmap/1.7"]),
            "payload_size_bytes": rng.randint(64, 4096),
        })
    return pd.DataFrame(rows)


# ── Schema canônico ───────────────────────────────────────────────────────────


class TestFeatureColumns:
    def test_feature_columns_list_nonempty(self) -> None:
        assert len(FEATURE_COLUMNS) > 0

    def test_feature_columns_contains_required(self) -> None:
        required = {
            "source_ip", "window_start",
            "auth_failure_rate", "auth_failure_count",
            "request_count", "unique_paths", "req_per_second", "scan_path_hits",
            "failure_ratio", "error_count", "timeout_ratio",
            "payload_size_mean", "payload_size_std",
            "inter_event_mean_ms", "inter_event_min_ms",
            "scanner_agent_ratio",
        }
        assert required.issubset(set(FEATURE_COLUMNS))

    def test_output_df_columns_match_feature_columns(self) -> None:
        events = [_make_event()]
        df = extract_features(events)
        assert list(df.columns) == FEATURE_COLUMNS

    def test_empty_df_columns_match_feature_columns(self) -> None:
        df = extract_features([])
        assert list(df.columns) == FEATURE_COLUMNS


# ── Novas features — valores ──────────────────────────────────────────────────


class TestAuthFailureCount:
    def test_auth_failure_count_correct(self) -> None:
        events = [
            _make_event("e1", status="failure", offset=0),
            _make_event("e2", status="failure", offset=10),
            _make_event("e3", status="success", offset=20),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["auth_failure_count"] == 2.0

    def test_auth_failure_count_zero_when_all_success(self) -> None:
        events = [_make_event(f"e{i}", status="success", offset=i * 10) for i in range(3)]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["auth_failure_count"] == 0.0


class TestReqPerSecond:
    def test_req_per_second_zero_when_no_http(self) -> None:
        events = [_make_event("e1", event_type="auth_attempt", status="success")]
        df = extract_features(events, window_seconds=60)
        assert df.iloc[0]["req_per_second"] == 0.0

    def test_req_per_second_formula(self) -> None:
        # 3 http_request, window=60s → req_per_second = 3/60
        events = [
            _make_event(f"e{i}", event_type="http_request", status="success", offset=i * 5)
            for i in range(3)
        ]
        df = extract_features(events, window_seconds=60)
        assert abs(df.iloc[0]["req_per_second"] - 3 / 60) < 1e-9


class TestScanPathHits:
    def test_scan_path_hits_known_path(self) -> None:
        events = [
            _make_event("e1", event_type="http_request", status="blocked",
                        request_path="/.env", offset=0),
            _make_event("e2", event_type="http_request", status="blocked",
                        request_path="/admin", offset=5),
            _make_event("e3", event_type="http_request", status="success",
                        request_path="/api/v1/login", offset=10),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["scan_path_hits"] == 2.0

    def test_scan_path_hits_zero_for_normal_paths(self) -> None:
        events = [
            _make_event("e1", event_type="http_request", status="success",
                        request_path="/api/v1/data", offset=0),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["scan_path_hits"] == 0.0

    def test_scan_path_hits_none_path_ignored(self) -> None:
        events = [_make_event("e1", event_type="http_request", status="success")]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["scan_path_hits"] == 0.0


class TestErrorCount:
    def test_error_count_includes_failure_and_blocked(self) -> None:
        events = [
            _make_event("e1", status="failure", offset=0),
            _make_event("e2", status="blocked", offset=5),
            _make_event("e3", status="success", offset=10),
            _make_event("e4", status="timeout", offset=15),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["error_count"] == 2.0

    def test_error_count_zero_when_all_success(self) -> None:
        events = [_make_event(f"e{i}", status="success", offset=i * 10) for i in range(3)]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["error_count"] == 0.0


class TestTimeoutRatio:
    def test_timeout_ratio_correct(self) -> None:
        events = [
            _make_event("e1", status="timeout", offset=0),
            _make_event("e2", status="timeout", offset=5),
            _make_event("e3", status="success", offset=10),
            _make_event("e4", status="success", offset=15),
        ]
        df = extract_features(events, window_seconds=300)
        assert abs(df.iloc[0]["timeout_ratio"] - 0.5) < 1e-9

    def test_timeout_ratio_zero_when_no_timeouts(self) -> None:
        events = [_make_event(f"e{i}", status="success", offset=i * 5) for i in range(3)]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["timeout_ratio"] == 0.0


class TestPayloadSizeStd:
    def test_payload_std_zero_for_single_event(self) -> None:
        df = extract_features([_make_event("e1", payload_size=100)])
        assert df.iloc[0]["payload_size_std"] == 0.0

    def test_payload_std_nonzero_for_different_sizes(self) -> None:
        events = [
            _make_event("e1", payload_size=100, offset=0),
            _make_event("e2", payload_size=900, offset=5),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["payload_size_std"] > 0.0

    def test_payload_std_zero_for_uniform_sizes(self) -> None:
        events = [_make_event(f"e{i}", payload_size=200, offset=i * 5) for i in range(4)]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["payload_size_std"] == 0.0


class TestInterEventStats:
    def test_inter_event_mean_ms_single_event(self) -> None:
        df = extract_features([_make_event("e1")])
        assert df.iloc[0]["inter_event_mean_ms"] == 0.0
        assert df.iloc[0]["inter_event_min_ms"] == 0.0

    def test_inter_event_mean_ms_two_events(self) -> None:
        # 2 eventos separados por 2 segundos = 2000ms
        events = [
            _make_event("e1", offset=0),
            _make_event("e2", offset=2),
        ]
        df = extract_features(events, window_seconds=300)
        assert abs(df.iloc[0]["inter_event_mean_ms"] - 2000.0) < 1.0
        assert abs(df.iloc[0]["inter_event_min_ms"] - 2000.0) < 1.0

    def test_inter_event_min_ms_is_minimum(self) -> None:
        # Intervalos: 1s, 5s, 1s → min=1000ms
        events = [
            _make_event("e1", offset=0),
            _make_event("e2", offset=1),    # +1s
            _make_event("e3", offset=6),    # +5s
            _make_event("e4", offset=7),    # +1s
        ]
        df = extract_features(events, window_seconds=300)
        assert abs(df.iloc[0]["inter_event_min_ms"] - 1000.0) < 1.0

    def test_inter_event_spike_pattern(self) -> None:
        """Traffic spike: eventos a cada 50ms → inter_event_mean ≈ 50ms."""
        base = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        events = []
        for i in range(5):
            ts = (base + timedelta(milliseconds=i * 50)).isoformat()
            events.append(LogEvent.model_validate({
                "event_id": f"spike-{i}",
                "timestamp": ts,
                "source_ip": "10.0.0.1",
                "event_type": "http_request",
                "status": "success",
                "metadata": {},
            }))
        df = extract_features(events, window_seconds=300)
        # Primeira janela deve ter inter_event_mean_ms ≈ 50ms
        assert df.iloc[0]["inter_event_mean_ms"] < 200.0


class TestScannerAgentRatio:
    def test_scanner_agent_ratio_sqlmap(self) -> None:
        events = [
            _make_event("e1", event_type="http_request", status="blocked",
                        user_agent="sqlmap/1.7.8", offset=0),
            _make_event("e2", event_type="http_request", status="success",
                        user_agent="Mozilla/5.0", offset=5),
        ]
        df = extract_features(events, window_seconds=300)
        assert abs(df.iloc[0]["scanner_agent_ratio"] - 0.5) < 1e-9

    def test_scanner_agent_ratio_zero_normal_agents(self) -> None:
        events = [
            _make_event("e1", user_agent="Mozilla/5.0 (Windows NT 10.0)", offset=0),
            _make_event("e2", user_agent="curl/7.88.1", offset=5),
        ]
        df = extract_features(events, window_seconds=300)
        # curl não está na lista de scanners (uso legítimo)
        assert df.iloc[0]["scanner_agent_ratio"] == 0.0

    def test_scanner_agent_ratio_none_user_agent(self) -> None:
        events = [_make_event("e1", user_agent=None)]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["scanner_agent_ratio"] == 0.0

    def test_scanner_agent_ratio_nikto(self) -> None:
        events = [
            _make_event("e1", user_agent="Nikto/2.1.6", event_type="http_request",
                        status="blocked", offset=0),
        ]
        df = extract_features(events, window_seconds=300)
        assert df.iloc[0]["scanner_agent_ratio"] == 1.0


# ── Helpers internos ──────────────────────────────────────────────────────────


class TestHelpers:
    def test_is_scanner_agent_sqlmap(self) -> None:
        assert _is_scanner_agent("sqlmap/1.7.8#stable")

    def test_is_scanner_agent_nikto(self) -> None:
        assert _is_scanner_agent("Nikto/2.1.6")

    def test_is_scanner_agent_mozilla_false(self) -> None:
        assert not _is_scanner_agent("Mozilla/5.0 (Windows NT 10.0)")

    def test_is_scanner_agent_curl_false(self) -> None:
        # curl tem uso legítimo → não deve ser classificado como scanner
        assert not _is_scanner_agent("curl/7.88.1")

    def test_is_scanner_agent_none_false(self) -> None:
        assert not _is_scanner_agent(None)

    def test_is_scan_path_env(self) -> None:
        assert _is_scan_path("/.env")

    def test_is_scan_path_normal_false(self) -> None:
        assert not _is_scan_path("/api/v1/login")

    def test_is_scan_path_none_false(self) -> None:
        assert not _is_scan_path(None)

    def test_compute_inter_event_stats_empty(self) -> None:
        mean, mn = _compute_inter_event_stats([])
        assert mean == 0.0
        assert mn == 0.0

    def test_compute_inter_event_stats_single(self) -> None:
        mean, mn = _compute_inter_event_stats([1000.0])
        assert mean == 0.0
        assert mn == 0.0

    def test_compute_inter_event_stats_uniform(self) -> None:
        ts = [0.0, 1000.0, 2000.0, 3000.0]
        mean, mn = _compute_inter_event_stats(ts)
        assert abs(mean - 1000.0) < 1e-6
        assert abs(mn - 1000.0) < 1e-6

    def test_compute_inter_event_stats_variable(self) -> None:
        ts = [0.0, 100.0, 600.0]  # diffs: 100, 500
        mean, mn = _compute_inter_event_stats(ts)
        assert abs(mean - 300.0) < 1e-6
        assert abs(mn - 100.0) < 1e-6


# ── Determinismo ──────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_output(self) -> None:
        events = [_make_event(f"e{i}", offset=i * 10) for i in range(5)]
        df1 = extract_features(events, window_seconds=300)
        df2 = extract_features(events, window_seconds=300)
        pd.testing.assert_frame_equal(df1, df2)

    def test_output_independent_of_input_order(self) -> None:
        """Mesmos eventos em ordem diferente devem produzir o mesmo conjunto de features."""
        events = [_make_event(f"e{i}", offset=i * 10) for i in range(5)]
        reversed_events = list(reversed(events))
        df1 = extract_features(events, window_seconds=300)
        df2 = extract_features(reversed_events, window_seconds=300)
        # Mesmo conjunto de (source_ip, window_start, feature) após ordenação
        df1_sorted = df1.sort_values(["source_ip", "window_start"]).reset_index(drop=True)
        df2_sorted = df2.sort_values(["source_ip", "window_start"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(df1_sorted, df2_sorted)


# ── Ausência de target leakage ────────────────────────────────────────────────


class TestNoTargetLeakage:
    """Garante que nenhuma função de feature usa metadata.label."""

    def test_extract_features_no_label_column(self) -> None:
        events = [_make_event("e1")]
        df = extract_features(events)
        assert "label" not in df.columns
        assert "metadata" not in df.columns

    def test_compute_volume_stats_no_label(self) -> None:
        df_raw = _make_raw_df(20)
        # Injeta label propositalmente para garantir que a função ignora
        df_raw["label"] = "injected_label"
        stats = compute_volume_stats(df_raw)
        # A função não deve retornar o label como chave
        assert "label" not in stats
        assert "injected_label" not in str(stats.values())

    def test_compute_request_frequency_no_label(self) -> None:
        df_raw = _make_raw_df(20)
        df_raw["label"] = "injected"
        result = compute_request_frequency(df_raw)
        assert "label" not in result.columns

    def test_compute_error_rate_no_label(self) -> None:
        df_raw = _make_raw_df(20)
        df_raw["label"] = "injected"
        result = compute_error_rate_by_type(df_raw)
        assert "label" not in result.columns

    def test_compute_endpoint_diversity_no_label(self) -> None:
        df_raw = _make_raw_df(20)
        df_raw["label"] = "injected"
        result = compute_endpoint_diversity(df_raw)
        assert "label" not in result.columns

    def test_compute_temporal_repetition_no_label(self) -> None:
        df_raw = _make_raw_df(20)
        df_raw["label"] = "injected"
        result = compute_temporal_repetition(df_raw)
        assert "label" not in result.columns


# ── compute_volume_stats ──────────────────────────────────────────────────────


class TestComputeVolumeStats:
    def test_total_events_correct(self) -> None:
        df = _make_raw_df(30)
        stats = compute_volume_stats(df)
        assert stats["total_events"] == 30

    def test_duplicate_detection(self) -> None:
        df = _make_raw_df(10)
        df = pd.concat([df, df.iloc[:3]], ignore_index=True)  # 3 duplicatas
        stats = compute_volume_stats(df)
        assert stats["duplicate_event_ids"] == 3

    def test_missing_per_column(self) -> None:
        df = _make_raw_df(10)
        df.loc[0, "request_path"] = None
        stats = compute_volume_stats(df)
        # request_path já pode ter None nos dados gerados — apenas verificamos o tipo
        assert isinstance(stats["missing_per_column"], dict)

    def test_date_range_hours_positive(self) -> None:
        df = _make_raw_df(20)
        stats = compute_volume_stats(df)
        assert stats["date_range_hours"] >= 0.0

    def test_empty_df(self) -> None:
        stats = compute_volume_stats(pd.DataFrame())
        assert stats["total_events"] == 0
        assert stats["unique_ips"] == 0


# ── compute_request_frequency ─────────────────────────────────────────────────


class TestComputeRequestFrequency:
    def test_returns_correct_columns(self) -> None:
        df = _make_raw_df(20)
        result = compute_request_frequency(df)
        assert set(result.columns) == {"source_ip", "window", "request_count"}

    def test_only_http_counted(self) -> None:
        df = _make_raw_df(20, seed=1)
        result = compute_request_frequency(df)
        # Todos os source_ip no resultado devem ter pelo menos 1 http_request
        http_ips = set(df[df["event_type"] == "http_request"]["source_ip"].unique())
        result_ips = set(result["source_ip"].unique())
        assert result_ips.issubset(http_ips)

    def test_sorted_descending(self) -> None:
        df = _make_raw_df(50, seed=2)
        result = compute_request_frequency(df)
        if len(result) > 1:
            assert result["request_count"].is_monotonic_decreasing or \
                   result["request_count"].iloc[0] >= result["request_count"].iloc[-1]

    def test_empty_df_returns_empty(self) -> None:
        result = compute_request_frequency(pd.DataFrame())
        assert result.empty

    def test_no_http_events_returns_empty(self) -> None:
        df = pd.DataFrame([{
            "source_ip": "1.1.1.1",
            "timestamp": "2025-01-15T08:00:00+00:00",
            "event_type": "auth_attempt",
            "status": "success",
        }])
        result = compute_request_frequency(df)
        assert result.empty


# ── compute_error_rate_by_type ────────────────────────────────────────────────


class TestComputeErrorRateByType:
    def test_returns_correct_columns(self) -> None:
        df = _make_raw_df(20)
        result = compute_error_rate_by_type(df)
        assert set(result.columns) == {"event_type", "total", "errors", "error_rate"}

    def test_error_rate_bounds(self) -> None:
        df = _make_raw_df(50)
        result = compute_error_rate_by_type(df)
        assert (result["error_rate"] >= 0.0).all()
        assert (result["error_rate"] <= 1.0).all()

    def test_all_success_zero_error_rate(self) -> None:
        df = pd.DataFrame([{
            "source_ip": "1.1.1.1",
            "timestamp": "2025-01-15T08:00:00+00:00",
            "event_type": "http_request",
            "status": "success",
        }])
        result = compute_error_rate_by_type(df)
        assert result.iloc[0]["error_rate"] == 0.0

    def test_all_failures_full_error_rate(self) -> None:
        df = pd.DataFrame([{
            "source_ip": "1.1.1.1",
            "timestamp": "2025-01-15T08:00:00+00:00",
            "event_type": "auth_attempt",
            "status": "failure",
        } for _ in range(5)])
        result = compute_error_rate_by_type(df)
        assert result.iloc[0]["error_rate"] == 1.0

    def test_empty_df_returns_empty(self) -> None:
        result = compute_error_rate_by_type(pd.DataFrame())
        assert result.empty


# ── compute_endpoint_diversity ────────────────────────────────────────────────


class TestComputeEndpointDiversity:
    def test_returns_correct_columns(self) -> None:
        df = _make_raw_df(20)
        result = compute_endpoint_diversity(df)
        assert set(result.columns) == {"request_path", "count", "pct"}

    def test_pct_sums_to_one(self) -> None:
        df = _make_raw_df(30)
        result = compute_endpoint_diversity(df)
        if not result.empty:
            assert abs(result["pct"].sum() - 1.0) < 1e-6

    def test_top_n_respected(self) -> None:
        df = _make_raw_df(100)
        result = compute_endpoint_diversity(df, top_n=5)
        assert len(result) <= 5

    def test_none_paths_excluded(self) -> None:
        df = pd.DataFrame({"request_path": [None, None, None]})
        result = compute_endpoint_diversity(df)
        assert result.empty

    def test_sorted_descending_by_count(self) -> None:
        df = _make_raw_df(50, seed=3)
        result = compute_endpoint_diversity(df)
        if len(result) > 1:
            assert result["count"].iloc[0] >= result["count"].iloc[-1]


# ── compute_temporal_repetition ───────────────────────────────────────────────


class TestComputeTemporalRepetition:
    def test_returns_correct_columns(self) -> None:
        df = _make_raw_df(20)
        result = compute_temporal_repetition(df)
        assert set(result.columns) == {"source_ip", "n_windows", "mean_events", "cv"}

    def test_cv_non_negative(self) -> None:
        df = _make_raw_df(50)
        result = compute_temporal_repetition(df)
        assert (result["cv"] >= 0.0).all()

    def test_sorted_by_n_windows_desc(self) -> None:
        df = _make_raw_df(50, seed=4)
        result = compute_temporal_repetition(df)
        if len(result) > 1:
            assert result["n_windows"].iloc[0] >= result["n_windows"].iloc[-1]

    def test_empty_df_returns_empty(self) -> None:
        result = compute_temporal_repetition(pd.DataFrame())
        assert result.empty

    def test_cv_zero_for_uniform_distribution(self) -> None:
        """IP com exatamente 1 evento por janela tem CV = 0."""
        base = datetime(2025, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
        rows = []
        for i in range(5):
            ts = base + timedelta(minutes=i * 5)
            rows.append({
                "source_ip": "10.0.0.1",
                "timestamp": ts.isoformat(),
                "event_type": "http_request",
                "status": "success",
            })
        df = pd.DataFrame(rows)
        result = compute_temporal_repetition(df, window_minutes=5)
        ip_row = result[result["source_ip"] == "10.0.0.1"]
        assert not ip_row.empty
        # CV deve ser zero (1 evento por janela → sem variação)
        assert ip_row.iloc[0]["cv"] == pytest.approx(0.0, abs=1e-6)
