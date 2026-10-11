"""Scoring e priorização de alertas do Sentinel.

Combina os sinais de regras (e futuramente de modelos ML) em um
score composto, determina a prioridade do alerta e monta o objeto Alert
com explicabilidade e limitações explícitas.

Score NÃO é uma probabilidade calibrada.
Não apresente o valor de score como probabilidade sem calibração documentada.
"""

from __future__ import annotations

from sentinel.config import settings
from sentinel.detection.rules import RuleMatch
from sentinel.schemas import Alert, AlertCategory, AlertPriority


# ── Mapeamento regra → categoria ───────────────────────────────────────────

_RULE_TO_CATEGORY: dict[str, AlertCategory] = {
    "brute_force": AlertCategory.BRUTE_FORCE,
    "traffic_spike": AlertCategory.TRAFFIC_SPIKE,
    "injection_attempt": AlertCategory.INJECTION_ATTEMPT,
}

# ── Limiares de prioridade ─────────────────────────────────────────────────

_PRIORITY_THRESHOLDS: list[tuple[float, AlertPriority]] = [
    (0.80, AlertPriority.CRITICAL),
    (0.55, AlertPriority.HIGH),
    (0.30, AlertPriority.MEDIUM),
    (0.00, AlertPriority.LOW),
]


def _compute_score(matches: list[RuleMatch]) -> float:
    """Calcula score composto a partir dos matches de regras.

    Estratégia: média ponderada das contribuições dos sinais,
    com boost para multiplicidade de categorias distintas.
    Score normalizado entre 0 e 1.
    """
    if not matches:
        return 0.0

    contributions = [m.signal.contribution for m in matches]
    base_score = sum(contributions) / len(contributions)

    # Boost por diversidade de categorias (até +0.20)
    distinct_rules = len({m.rule_name for m in matches})
    diversity_boost = min(0.20, (distinct_rules - 1) * 0.10)

    return min(1.0, base_score + diversity_boost)


def _determine_priority(score: float) -> AlertPriority:
    """Mapeia um score numérico para um nível de prioridade."""
    for threshold, priority in _PRIORITY_THRESHOLDS:
        if score >= threshold:
            return priority
    return AlertPriority.LOW


def _determine_category(matches: list[RuleMatch]) -> AlertCategory:
    """Determina categoria principal pelo match de maior contribuição."""
    if not matches:
        return AlertCategory.UNKNOWN
    dominant = max(matches, key=lambda m: m.signal.contribution)
    return _RULE_TO_CATEGORY.get(dominant.rule_name, AlertCategory.UNKNOWN)


_LIMITATIONS_TEMPLATE = (
    "Score calculado a partir de regras heurísticas com limiares fixos "
    "(min_failures={min_failures}, score_threshold={threshold}). "
    "Sem calibração estatística: o valor numérico não representa uma probabilidade. "
    "Falsos positivos são esperados, especialmente em ambientes com tráfego legítimo elevado. "
    "Revise os sinais antes de tomar ação."
)


def score_matches(
    matches: list[RuleMatch],
    model_version: str = "rules-only",
) -> Alert | None:
    """Converte uma lista de RuleMatch em um Alert priorizado.

    Retorna None se não houver matches ou se o score ficar abaixo do limiar
    configurado em settings.alert_score_threshold.

    Args:
        matches: Resultados das regras para o batch.
        model_version: Versão do conjunto de regras/modelo utilizado.

    Returns:
        Alert priorizado com signals e limitações, ou None.
    """
    if not matches:
        return None

    score = _compute_score(matches)

    if score < settings.alert_score_threshold:
        return None

    signals = [m.signal for m in matches]
    source_event_ids: list[str] = []
    for m in matches:
        source_event_ids.extend(m.matched_event_ids)
    # Remove duplicatas preservando ordem
    seen: set[str] = set()
    unique_ids = [eid for eid in source_event_ids if not (eid in seen or seen.add(eid))]  # type: ignore[func-returns-value]

    return Alert(
        category=_determine_category(matches),
        priority=_determine_priority(score),
        score=round(score, 4),
        signals=signals,
        source_event_ids=unique_ids,
        limitations=_LIMITATIONS_TEMPLATE.format(
            min_failures=settings.rule_min_attempts,
            threshold=settings.alert_score_threshold,
        ),
        model_version=model_version,
    )
