"""Testes unitários — src/sentinel/detection/rules.py"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sentinel.detection.rules import (
    BruteForceRule,
    InjectionRule,
    RuleMatch,
    TrafficSpikeRule,
    apply_rules,
)
from sentinel.schemas import LogEvent


# ── Helpers ────────────────────────────────────────────────────────────────


def _ts(offset_seconds: int = 0) -> str:
    """Timestamp UTC com offset em segundos a partir de um ponto base."""
    base = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).isoformat()


def _make_auth(
    event_id: str,
    ip: str = "10.0.0.1",
    status: str = "failure",
    offset: int = 0,
) -> LogEvent:
    return LogEvent.model_validate({
        "event_id": event_id,
        "timestamp": _ts(offset),
        "source_ip": ip,
        "event_type": "auth_attempt",
        "status": status,
        "metadata": {},
    })


def _make_http(
    event_id: str,
    ip: str = "10.0.0.2",
    path: str = "/api/v1/data",
    status: str = "success",
    offset: int = 0,
    user_agent: str = "Mozilla/5.0",
) -> LogEvent:
    return LogEvent.model_validate({
        "event_id": event_id,
        "timestamp": _ts(offset),
        "source_ip": ip,
        "event_type": "http_request",
        "status": status,
        "request_path": path,
        "user_agent": user_agent,
        "metadata": {},
    })


# ── BruteForceRule ─────────────────────────────────────────────────────────


class TestBruteForceRule:
    rule = BruteForceRule(min_failures=5, window_seconds=300)

    def test_fires_when_n_equals_min(self) -> None:
        """Exatamente min_failures dentro da janela deve disparar."""
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert len(matches) == 1

    def test_fires_when_n_exceeds_min(self) -> None:
        """Mais que min_failures dentro da janela deve disparar."""
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(10)]
        matches = self.rule.evaluate(events)
        assert len(matches) == 1

    def test_does_not_fire_below_threshold(self) -> None:
        """Menos que min_failures não deve disparar."""
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(4)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_does_not_fire_outside_window(self) -> None:
        """Falhas espalhadas além da janela não devem disparar."""
        # 5 falhas com 100s de distância cada = 400s no total > window_seconds=300
        events = [_make_auth(f"e{i}", offset=i * 100) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_does_not_fire_on_success(self) -> None:
        """Tentativas bem-sucedidas não contam para brute force."""
        events = [_make_auth(f"e{i}", status="success", offset=i * 5) for i in range(10)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_does_not_fire_for_non_auth_events(self) -> None:
        """Eventos que não são auth_attempt são ignorados."""
        events = [_make_http(f"e{i}", offset=i * 5) for i in range(10)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_isolates_by_ip(self) -> None:
        """IPs distintos são avaliados separadamente."""
        # IP A: 3 falhas — abaixo do limiar
        events_a = [_make_auth(f"a{i}", ip="1.1.1.1", offset=i * 10) for i in range(3)]
        # IP B: 5 falhas — acima do limiar
        events_b = [_make_auth(f"b{i}", ip="2.2.2.2", offset=i * 10) for i in range(5)]
        matches = self.rule.evaluate(events_a + events_b)
        # Somente IP B deve disparar
        assert len(matches) == 1
        assert all("2.2.2.2" not in m.rule_name for m in matches)  # verifica que é brute_force
        assert matches[0].rule_name == "brute_force"

    def test_signal_name(self) -> None:
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert matches[0].signal.name == "repeated_auth_failures"

    def test_signal_value_equals_burst_count(self) -> None:
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(7)]
        matches = self.rule.evaluate(events)
        assert matches[0].signal.value == 7.0

    def test_signal_threshold_matches_config(self) -> None:
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert matches[0].signal.threshold == 5.0

    def test_contribution_between_0_and_1(self) -> None:
        events = [_make_auth(f"e{i}", offset=i * 10) for i in range(20)]
        matches = self.rule.evaluate(events)
        assert 0.0 <= matches[0].signal.contribution <= 1.0

    def test_one_match_per_ip(self) -> None:
        """Mesmo com muitas falhas, apenas 1 match por IP."""
        events = [_make_auth(f"e{i}", offset=i * 5) for i in range(30)]
        matches = self.rule.evaluate(events)
        assert len(matches) == 1

    def test_empty_batch_returns_empty(self) -> None:
        assert self.rule.evaluate([]) == []

    def test_matched_event_ids_populated(self) -> None:
        events = [_make_auth(f"evt-{i}", offset=i * 10) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert len(matches[0].matched_event_ids) >= 5


# ── TrafficSpikeRule ───────────────────────────────────────────────────────


class TestTrafficSpikeRule:
    rule = TrafficSpikeRule(request_threshold=5, window_seconds=60)

    def test_fires_when_n_equals_threshold(self) -> None:
        events = [_make_http(f"r{i}", offset=i * 5) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert len(matches) == 1

    def test_fires_when_n_exceeds_threshold(self) -> None:
        events = [_make_http(f"r{i}", offset=i * 5) for i in range(10)]
        matches = self.rule.evaluate(events)
        assert len(matches) == 1

    def test_does_not_fire_below_threshold(self) -> None:
        events = [_make_http(f"r{i}", offset=i * 5) for i in range(4)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_does_not_fire_outside_window(self) -> None:
        # 5 requests com 20s de distância = 80s > window=60s
        events = [_make_http(f"r{i}", offset=i * 20) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_does_not_fire_for_auth_events(self) -> None:
        """auth_attempt não conta para traffic spike."""
        events = [_make_auth(f"a{i}", offset=i * 5) for i in range(10)]
        matches = self.rule.evaluate(events)
        assert matches == []

    def test_isolates_by_ip(self) -> None:
        """IPs distintos avaliados separadamente."""
        low_traffic = [_make_http(f"l{i}", ip="1.1.1.1", offset=i * 5) for i in range(3)]
        high_traffic = [_make_http(f"h{i}", ip="2.2.2.2", offset=i * 5) for i in range(5)]
        matches = self.rule.evaluate(low_traffic + high_traffic)
        assert len(matches) == 1

    def test_signal_name(self) -> None:
        events = [_make_http(f"r{i}", offset=i * 5) for i in range(5)]
        matches = self.rule.evaluate(events)
        assert matches[0].signal.name == "high_request_volume"

    def test_contribution_between_0_and_1(self) -> None:
        events = [_make_http(f"r{i}", offset=i * 5) for i in range(20)]
        matches = self.rule.evaluate(events)
        assert 0.0 <= matches[0].signal.contribution <= 1.0

    def test_empty_batch_returns_empty(self) -> None:
        assert self.rule.evaluate([]) == []


# ── InjectionRule ──────────────────────────────────────────────────────────


class TestInjectionRule:
    rule = InjectionRule()

    def test_detects_sql_injection_in_path(self) -> None:
        evt = _make_http("inj-sql", path="/?q=1' OR '1'='1")
        matches = self.rule.evaluate([evt])
        assert len(matches) == 1
        assert "sql" in matches[0].signal.name

    def test_detects_path_traversal(self) -> None:
        evt = _make_http("inj-pt", path="/../etc/passwd")
        matches = self.rule.evaluate([evt])
        assert len(matches) == 1
        assert "path_traversal" in matches[0].signal.name

    def test_detects_xss_in_path(self) -> None:
        evt = _make_http("inj-xss", path="/?s=<script>alert(1)</script>")
        matches = self.rule.evaluate([evt])
        assert len(matches) == 1
        assert "xss" in matches[0].signal.name

    def test_detects_sql_in_user_agent(self) -> None:
        evt = _make_http("inj-ua", user_agent="sqlmap/1.7")
        matches = self.rule.evaluate([evt])
        assert len(matches) == 1

    def test_does_not_fire_on_normal_path(self) -> None:
        evt = _make_http("normal", path="/api/v1/users")
        matches = self.rule.evaluate([evt])
        assert matches == []

    def test_does_not_fire_on_auth_events(self) -> None:
        """auth_attempt não é avaliado pela InjectionRule."""
        evt = _make_auth("auth-evt")
        matches = self.rule.evaluate([evt])
        assert matches == []

    def test_contribution_between_0_and_1(self) -> None:
        evt = _make_http("inj-contrib", path="/?q=select * from users")
        matches = self.rule.evaluate([evt])
        assert 0.0 <= matches[0].signal.contribution <= 1.0

    def test_multiple_patterns_one_match_per_event(self) -> None:
        """Múltiplos padrões no mesmo evento geram 1 match (não N)."""
        evt = _make_http("inj-multi", path="/?q=1' OR '1'='1 <script>")
        matches = self.rule.evaluate([evt])
        assert len(matches) == 1

    def test_matched_event_id_correct(self) -> None:
        evt = _make_http("inj-id", path="/../etc/passwd")
        matches = self.rule.evaluate([evt])
        assert matches[0].matched_event_ids == ["inj-id"]

    def test_empty_batch_returns_empty(self) -> None:
        assert self.rule.evaluate([]) == []


# ── apply_rules (pipeline) ─────────────────────────────────────────────────


class TestApplyRules:
    def test_returns_empty_for_clean_batch(self) -> None:
        events = [_make_http(f"ok{i}", offset=i * 60) for i in range(3)]
        matches = apply_rules(events)
        assert matches == []

    def test_runs_all_default_rules(self) -> None:
        """Batch com brute force + injection deve ter matches de ambas as regras."""
        bf_events = [_make_auth(f"bf{i}", offset=i * 10) for i in range(5)]
        inj_event = _make_http("inj", path="/?q=1' OR '1'='1")
        matches = apply_rules(bf_events + [inj_event])
        rule_names = {m.rule_name for m in matches}
        assert "brute_force" in rule_names
        assert "injection_attempt" in rule_names

    def test_custom_rules_override_defaults(self) -> None:
        """Regras personalizadas substituem DEFAULT_RULES."""
        events = [_make_auth(f"bf{i}", offset=i * 10) for i in range(5)]
        # Somente TrafficSpikeRule — não deve disparar para auth events
        matches = apply_rules(events, rules=[TrafficSpikeRule(request_threshold=5)])
        assert matches == []

    def test_empty_batch_returns_empty(self) -> None:
        assert apply_rules([]) == []
