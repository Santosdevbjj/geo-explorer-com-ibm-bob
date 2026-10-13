"""Regras de detecção explícitas e auditáveis do Sentinel.

Cada regra recebe uma lista de LogEvent e retorna zero ou mais Signal.
Regras são intencionalmente simples e legíveis: sem lógica oculta.

Regras implementadas:
- BruteForceRule      : N falhas de autenticação do mesmo IP em janela T
- TrafficSpikeRule    : volume de requisições HTTP acima do limiar por IP
- InjectionRule       : padrões de SQL injection, XSS e path traversal
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from sentinel.schemas import EventStatus, EventType, LogEvent, Signal, SignalSource

# ── Resultado de uma regra ─────────────────────────────────────────────────


@dataclass
class RuleMatch:
    """Resultado quando uma regra dispara para um conjunto de eventos."""

    rule_name: str
    signal: Signal
    matched_event_ids: list[str] = field(default_factory=list)


# ── Regra base ─────────────────────────────────────────────────────────────


class BaseRule:
    """Interface mínima que todas as regras implementam."""

    name: str = "base_rule"

    def evaluate(self, events: list[LogEvent]) -> list[RuleMatch]:  # pragma: no cover
        raise NotImplementedError


# ── Brute Force ────────────────────────────────────────────────────────────


class BruteForceRule(BaseRule):
    """Detecta rajadas de falhas de autenticação do mesmo IP.

    Dispara quando um único source_ip acumula >= min_failures tentativas
    com status 'failure' dentro de uma janela deslizante de window_seconds.
    """

    name = "brute_force"

    def __init__(self, min_failures: int = 5, window_seconds: int = 300) -> None:
        self.min_failures = min_failures
        self.window_seconds = window_seconds

    def evaluate(self, events: list[LogEvent]) -> list[RuleMatch]:
        auth_failures: dict[str, list[LogEvent]] = defaultdict(list)

        for evt in events:
            if (
                evt.event_type == EventType.AUTH_ATTEMPT
                and evt.status == EventStatus.FAILURE
            ):
                auth_failures[str(evt.source_ip)].append(evt)

        matches: list[RuleMatch] = []
        window = timedelta(seconds=self.window_seconds)

        for _ip, failures in auth_failures.items():
            failures_sorted = sorted(failures, key=lambda e: e.timestamp)
            # Janela deslizante O(n²) — aceitável para batches analíticos
            for i, anchor in enumerate(failures_sorted):
                window_end = anchor.timestamp + window
                burst = [e for e in failures_sorted[i:] if e.timestamp <= window_end]
                if len(burst) >= self.min_failures:
                    matches.append(
                        RuleMatch(
                            rule_name=self.name,
                            signal=Signal(
                                name="repeated_auth_failures",
                                source=SignalSource.RULE,
                                value=float(len(burst)),
                                threshold=float(self.min_failures),
                                contribution=min(
                                    1.0, len(burst) / (self.min_failures * 3)
                                ),
                            ),
                            matched_event_ids=[e.event_id for e in burst],
                        )
                    )
                    break  # uma correspondência por IP é suficiente

        return matches


# ── Traffic Spike ──────────────────────────────────────────────────────────


class TrafficSpikeRule(BaseRule):
    """Detecta volume anormal de requisições HTTP de um único IP.

    Dispara quando um source_ip envia >= request_threshold requisições
    http_request em qualquer janela de window_seconds.
    """

    name = "traffic_spike"

    def __init__(self, request_threshold: int = 100, window_seconds: int = 60) -> None:
        self.request_threshold = request_threshold
        self.window_seconds = window_seconds

    def evaluate(self, events: list[LogEvent]) -> list[RuleMatch]:
        http_events: dict[str, list[LogEvent]] = defaultdict(list)

        for evt in events:
            if evt.event_type == EventType.HTTP_REQUEST:
                http_events[str(evt.source_ip)].append(evt)

        matches: list[RuleMatch] = []
        window = timedelta(seconds=self.window_seconds)

        for _ip, reqs in http_events.items():
            reqs_sorted = sorted(reqs, key=lambda e: e.timestamp)
            for i, anchor in enumerate(reqs_sorted):
                window_end = anchor.timestamp + window
                burst = [e for e in reqs_sorted[i:] if e.timestamp <= window_end]
                if len(burst) >= self.request_threshold:
                    matches.append(
                        RuleMatch(
                            rule_name=self.name,
                            signal=Signal(
                                name="high_request_volume",
                                source=SignalSource.RULE,
                                value=float(len(burst)),
                                threshold=float(self.request_threshold),
                                contribution=min(
                                    1.0, len(burst) / (self.request_threshold * 2)
                                ),
                            ),
                            matched_event_ids=[e.event_id for e in burst],
                        )
                    )
                    break

        return matches


# ── Injection ──────────────────────────────────────────────────────────────

# Padrões compilados uma única vez (custo de compilação pago no import)
_SQL_PATTERN = re.compile(
    r"(\bsqlmap\b|\bunion\b|\bselect\b|\bdrop\b|\binsert\b|\bupdate\b|--|'|\bor\b\s+['\"0-9])",
    re.IGNORECASE,
)
_XSS_PATTERN = re.compile(r"<\s*script|javascript\s*:|on\w+\s*=", re.IGNORECASE)
_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\|%2e%2e[%/\\]", re.IGNORECASE)


class InjectionRule(BaseRule):
    """Detecta tentativas de injeção em request_path e user_agent.

    Cobre: SQL injection, XSS, path traversal.
    Regra de heurística — pode gerar falsos positivos em payloads legítimos
    que contenham palavras-chave SQL (ex: nomes de campos).
    """

    name = "injection_attempt"

    def evaluate(self, events: list[LogEvent]) -> list[RuleMatch]:
        matches: list[RuleMatch] = []

        for evt in events:
            if evt.event_type != EventType.HTTP_REQUEST:
                continue

            targets = [
                evt.request_path or "",
                evt.user_agent or "",
            ]
            combined = " ".join(targets)

            detected: list[str] = []
            if _SQL_PATTERN.search(combined):
                detected.append("sql_injection_pattern")
            if _XSS_PATTERN.search(combined):
                detected.append("xss_pattern")
            if _PATH_TRAVERSAL_PATTERN.search(combined):
                detected.append("path_traversal_pattern")

            if detected:
                matches.append(
                    RuleMatch(
                        rule_name=self.name,
                        signal=Signal(
                            name=detected[0],
                            source=SignalSource.RULE,
                            value=float(len(detected)),
                            threshold=1.0,
                            contribution=min(1.0, 0.3 * len(detected)),
                        ),
                        matched_event_ids=[evt.event_id],
                    )
                )

        return matches


# ── Pipeline de regras ─────────────────────────────────────────────────────


DEFAULT_RULES: list[BaseRule] = [
    BruteForceRule(),
    TrafficSpikeRule(),
    InjectionRule(),
]


def apply_rules(
    events: list[LogEvent],
    rules: list[BaseRule] | None = None,
) -> list[RuleMatch]:
    """Executa todas as regras sobre o batch e retorna os matches encontrados.

    Args:
        events: Lista de eventos já validados.
        rules: Lista de regras a aplicar. Usa DEFAULT_RULES se None.

    Returns:
        Lista de RuleMatch (pode ser vazia se nenhuma regra disparar).
    """
    active_rules = rules if rules is not None else DEFAULT_RULES
    all_matches: list[RuleMatch] = []
    for rule in active_rules:
        all_matches.extend(rule.evaluate(events))
    return all_matches
