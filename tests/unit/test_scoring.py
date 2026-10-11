"""Testes unitários — src/sentinel/detection/scoring.py"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sentinel.detection.rules import BruteForceRule, InjectionRule, RuleMatch
from sentinel.detection.scoring import (
    _compute_score,
    _determine_category,
    _determine_priority,
    score_matches,
)
from sentinel.schemas import (
    Alert,
    AlertCategory,
    AlertPriority,
    LogEvent,
    Signal,
    SignalSource,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_match(
    rule_name: str = "brute_force",
    contribution: float = 0.8,
    signal_name: str = "repeated_auth_failures",
) -> RuleMatch:
    return RuleMatch(
        rule_name=rule_name,
        signal=Signal(
            name=signal_name,
            source=SignalSource.RULE,
            value=10.0,
            threshold=5.0,
            contribution=contribution,
        ),
        matched_event_ids=["evt-001"],
    )


def _make_auth_events(n: int = 5, ip: str = "10.0.0.1") -> list[LogEvent]:
    base = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return [
        LogEvent.model_validate({
            "event_id": f"bf-{i}",
            "timestamp": (base + timedelta(seconds=i * 10)).isoformat(),
            "source_ip": ip,
            "event_type": "auth_attempt",
            "status": "failure",
            "metadata": {},
        })
        for i in range(n)
    ]


# ── _compute_score ─────────────────────────────────────────────────────────


class TestComputeScore:
    def test_empty_matches_returns_zero(self) -> None:
        assert _compute_score([]) == 0.0

    def test_single_match_no_boost(self) -> None:
        """Um único match → score = contribution (sem diversity boost)."""
        match = _make_match(contribution=0.5)
        score = _compute_score([match])
        assert score == 0.5

    def test_diversity_boost_two_categories(self) -> None:
        """Dois tipos de regra distintos devem ter boost > 0."""
        m1 = _make_match(rule_name="brute_force", contribution=0.5)
        m2 = _make_match(rule_name="injection_attempt", contribution=0.5, signal_name="sql")
        score_single = _compute_score([m1])
        score_both = _compute_score([m1, m2])
        assert score_both > score_single

    def test_score_never_exceeds_1(self) -> None:
        """Score normalizado em [0, 1]."""
        matches = [_make_match(contribution=1.0) for _ in range(5)]
        assert _compute_score(matches) <= 1.0

    def test_score_never_below_0(self) -> None:
        match = _make_match(contribution=0.0)
        assert _compute_score([match]) >= 0.0

    def test_diversity_boost_capped_at_0_20(self) -> None:
        """Boost máximo de 0.20 independente do número de categorias."""
        matches = [
            _make_match(rule_name=f"rule_{i}", contribution=0.5)
            for i in range(10)
        ]
        score = _compute_score(matches)
        # base=0.5, boost máximo=0.20 → máximo esperado = 0.70
        assert score <= 0.70 + 1e-9


# ── _determine_priority ────────────────────────────────────────────────────


class TestDeterminePriority:
    def test_critical_at_0_80(self) -> None:
        assert _determine_priority(0.80) == AlertPriority.CRITICAL

    def test_critical_at_1_0(self) -> None:
        assert _determine_priority(1.0) == AlertPriority.CRITICAL

    def test_high_at_0_55(self) -> None:
        assert _determine_priority(0.55) == AlertPriority.HIGH

    def test_high_at_0_79(self) -> None:
        assert _determine_priority(0.79) == AlertPriority.HIGH

    def test_medium_at_0_30(self) -> None:
        assert _determine_priority(0.30) == AlertPriority.MEDIUM

    def test_medium_at_0_54(self) -> None:
        assert _determine_priority(0.54) == AlertPriority.MEDIUM

    def test_low_at_0_00(self) -> None:
        assert _determine_priority(0.00) == AlertPriority.LOW

    def test_low_at_0_29(self) -> None:
        assert _determine_priority(0.29) == AlertPriority.LOW


# ── _determine_category ────────────────────────────────────────────────────


class TestDetermineCategory:
    def test_empty_returns_unknown(self) -> None:
        assert _determine_category([]) == AlertCategory.UNKNOWN

    def test_brute_force_match(self) -> None:
        match = _make_match(rule_name="brute_force", contribution=0.8)
        assert _determine_category([match]) == AlertCategory.BRUTE_FORCE

    def test_traffic_spike_match(self) -> None:
        match = _make_match(rule_name="traffic_spike", contribution=0.6, signal_name="high_volume")
        assert _determine_category([match]) == AlertCategory.TRAFFIC_SPIKE

    def test_injection_match(self) -> None:
        match = _make_match(rule_name="injection_attempt", contribution=0.9, signal_name="sql")
        assert _determine_category([match]) == AlertCategory.INJECTION_ATTEMPT

    def test_dominant_category_wins(self) -> None:
        """Quando dois matches, a categoria com maior contribuição vence."""
        low = _make_match(rule_name="brute_force", contribution=0.3)
        high = _make_match(rule_name="injection_attempt", contribution=0.9, signal_name="sql")
        assert _determine_category([low, high]) == AlertCategory.INJECTION_ATTEMPT

    def test_unknown_rule_name_returns_unknown(self) -> None:
        match = _make_match(rule_name="nonexistent_rule", contribution=0.9)
        assert _determine_category([match]) == AlertCategory.UNKNOWN


# ── score_matches ──────────────────────────────────────────────────────────


class TestScoreMatches:
    def test_empty_matches_returns_none(self) -> None:
        assert score_matches([]) is None

    def test_returns_none_below_threshold(self) -> None:
        """Score abaixo do threshold configurado deve retornar None."""
        # Contribution baixíssima → score abaixo de qualquer threshold razoável
        match = _make_match(contribution=0.01)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.5
            mock_settings.rule_min_attempts = 5
            result = score_matches([match])
        assert result is None

    def test_returns_alert_above_threshold(self) -> None:
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.3
            mock_settings.rule_min_attempts = 5
            result = score_matches([match])
        assert result is not None
        assert isinstance(result, Alert)

    def test_alert_has_at_least_one_signal(self) -> None:
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match])
        assert alert is not None
        assert len(alert.signals) >= 1

    def test_alert_limitations_not_empty(self) -> None:
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match])
        assert alert is not None
        assert len(alert.limitations) > 0

    def test_alert_score_between_0_and_1(self) -> None:
        matches = [_make_match(contribution=0.9), _make_match(contribution=0.8, rule_name="traffic_spike")]
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches(matches)
        assert alert is not None
        assert 0.0 <= alert.score <= 1.0

    def test_alert_score_not_presented_as_probability(self) -> None:
        """limitations deve conter texto sobre calibração."""
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match])
        assert alert is not None
        # O texto de limitações deve mencionar que não é probabilidade
        assert "probabilidade" in alert.limitations.lower() or "calibra" in alert.limitations.lower()

    def test_model_version_default(self) -> None:
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match])
        assert alert is not None
        assert alert.model_version == "rules-only"

    def test_custom_model_version(self) -> None:
        match = _make_match(contribution=0.9)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match], model_version="isolation-forest-v1")
        assert alert is not None
        assert alert.model_version == "isolation-forest-v1"

    def test_source_event_ids_populated(self) -> None:
        match = _make_match(contribution=0.9)
        match.matched_event_ids = ["id-1", "id-2"]
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([match])
        assert alert is not None
        assert "id-1" in alert.source_event_ids
        assert "id-2" in alert.source_event_ids

    def test_duplicate_event_ids_deduplicated(self) -> None:
        """Mesmo ID em dois matches distintos deve aparecer uma vez."""
        m1 = _make_match(contribution=0.5)
        m1.matched_event_ids = ["shared-id"]
        m2 = _make_match(rule_name="traffic_spike", contribution=0.5, signal_name="vol")
        m2.matched_event_ids = ["shared-id"]
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches([m1, m2])
        assert alert is not None
        assert alert.source_event_ids.count("shared-id") == 1

    def test_end_to_end_with_real_rules(self) -> None:
        """Score gerado a partir de regras reais com eventos reais."""
        events = _make_auth_events(n=8)
        rule = BruteForceRule(min_failures=5, window_seconds=300)
        matches = rule.evaluate(events)
        with patch("sentinel.detection.scoring.settings") as mock_settings:
            mock_settings.alert_score_threshold = 0.1
            mock_settings.rule_min_attempts = 5
            alert = score_matches(matches)
        assert alert is not None
        assert 0.0 <= alert.score <= 1.0
        assert alert.category == AlertCategory.BRUTE_FORCE
