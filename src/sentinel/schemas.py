"""Contratos de dados (schemas Pydantic v2) do Sentinel.

Hierarquia:
    LogEvent       → entrada do pipeline (evento de log bruto)
    Signal         → sinal de detecção (regra ou modelo)
    Alert          → saída do pipeline (alerta priorizado e explicável)
    ValidationReport → resultado da etapa de validação de dados
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic.networks import IPvAnyAddress

# ── Enumerações ────────────────────────────────────────────────────────────


class EventType(StrEnum):
    """Tipos de evento suportados pelo Sentinel."""

    AUTH_ATTEMPT = "auth_attempt"
    HTTP_REQUEST = "http_request"
    DNS_QUERY = "dns_query"
    NETWORK_FLOW = "network_flow"


class EventStatus(StrEnum):
    """Resultado do evento."""

    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"


class Protocol(StrEnum):
    """Protocolos de rede reconhecidos."""

    TCP = "TCP"
    UDP = "UDP"
    ICMP = "ICMP"
    HTTP = "HTTP"
    HTTPS = "HTTPS"


class AlertCategory(StrEnum):
    """Categorias de alerta geradas pelo Sentinel."""

    BRUTE_FORCE = "brute_force"
    TRAFFIC_SPIKE = "traffic_spike"
    INJECTION_ATTEMPT = "injection_attempt"
    ANOMALY = "anomaly"
    UNKNOWN = "unknown"


class AlertPriority(StrEnum):
    """Níveis de prioridade de um alerta."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SignalSource(StrEnum):
    """Origem do sinal de detecção."""

    RULE = "rule"
    MODEL = "model"


# ── Modelos de entrada ─────────────────────────────────────────────────────


class LogEvent(BaseModel):
    """Evento de log recebido pelo pipeline do Sentinel.

    Todos os campos com valor padrão ``None`` são opcionais.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único do evento (UUID).",
    )
    timestamp: datetime = Field(
        description="Momento do evento. Deve incluir timezone (preferencialmente UTC).",
    )
    source_ip: IPvAnyAddress = Field(description="IP de origem da requisição.")
    dest_ip: IPvAnyAddress | None = Field(default=None, description="IP de destino.")
    dest_port: int | None = Field(
        default=None, ge=1, le=65535, description="Porta de destino."
    )
    protocol: Protocol | None = Field(default=None, description="Protocolo de rede.")
    event_type: EventType = Field(description="Tipo do evento.")
    status: EventStatus = Field(description="Resultado do evento.")
    user_id: str | None = Field(
        default=None, description="Identificador anonimizado do usuário."
    )
    payload_size_bytes: int | None = Field(
        default=None, ge=0, description="Tamanho do payload em bytes."
    )
    user_agent: str | None = Field(default=None, description="User-agent HTTP.")
    request_path: str | None = Field(
        default=None, description="Caminho da requisição HTTP."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Campos adicionais livres."
    )

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        """Garante que o timestamp sempre carrega informação de timezone."""
        if v.tzinfo is None:
            raise ValueError(
                "timestamp deve incluir timezone. Use UTC (ex: 2025-01-15T14:23:00Z)."
            )
        return v.astimezone(UTC)


# ── Modelos de saída ───────────────────────────────────────────────────────


class Signal(BaseModel):
    """Sinal de detecção que contribuiu para um alerta.

    Componente central de explicabilidade — cada alerta deve ter pelo menos um sinal.
    """

    name: str = Field(
        description="Nome descritivo do sinal (ex: 'repeated_auth_failures')."
    )
    source: SignalSource = Field(
        description="Origem do sinal: regra explícita ou modelo ML."
    )
    value: float = Field(
        description="Valor numérico observado (ex: contagem de falhas)."
    )
    threshold: float = Field(description="Limiar que ativou o sinal.")
    contribution: float = Field(
        ge=0.0,
        le=1.0,
        description="Contribuição relativa deste sinal para o score final (0–1).",
    )


class Alert(BaseModel):
    """Alerta priorizado e explicável gerado pelo Sentinel.

    Campos de explicabilidade obrigatórios:
    - ``signals``: pelo menos um sinal deve estar presente
    - ``limitations``: texto explícito sobre o que este alerta NÃO garante

    IMPORTANTE: ``score`` não é uma probabilidade calibrada.
    Não o apresente como probabilidade real sem calibração documentada.
    """

    alert_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Identificador único do alerta.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp de geração do alerta (UTC).",
    )
    category: AlertCategory = Field(description="Categoria do comportamento detectado.")
    priority: AlertPriority = Field(description="Nível de prioridade do alerta.")
    score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Score composto (0–1). "
            "NÃO é uma probabilidade calibrada — ver 'limitations'."
        ),
    )
    signals: list[Signal] = Field(
        min_length=1,
        description="Sinais que contribuíram para este alerta. Pelo menos um obrigatório.",
    )
    source_event_ids: list[str] = Field(
        default_factory=list,
        description="IDs dos eventos de log que originaram este alerta.",
    )
    limitations: str = Field(
        description=(
            "Texto explícito sobre as limitações desta avaliação. "
            "Ex: 'Score baseado em regras heurísticas sem calibração estatística.'"
        ),
    )
    model_version: str = Field(
        default="rules-only",
        description="Versão do modelo ou conjunto de regras utilizado.",
    )


# ── Relatório de validação ─────────────────────────────────────────────────


class FieldError(BaseModel):
    """Erro em um campo específico de um registro."""

    field: str
    error: str
    value: Any | None = None


class InvalidRecord(BaseModel):
    """Registro inválido identificado durante a validação."""

    record_index: int
    event_id: str | None
    errors: list[FieldError]


class ValidationReport(BaseModel):
    """Resultado da etapa de validação de um batch de eventos.

    Expõe contagens e listas detalhadas — nunca descarta registros silenciosamente.
    """

    total_records: int = Field(description="Total de registros no batch.")
    valid_records: int = Field(
        description="Registros que passaram em todas as validações."
    )
    invalid_records: int = Field(
        description="Registros com pelo menos um erro de validação."
    )
    duplicate_ids: list[str] = Field(
        default_factory=list,
        description="IDs de eventos duplicados encontrados.",
    )
    missing_fields_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Contagem de valores ausentes por campo obrigatório.",
    )
    invalid_record_details: list[InvalidRecord] = Field(
        default_factory=list,
        description="Detalhes de cada registro inválido.",
    )
    passed: bool = Field(
        description="True somente se não houver registros inválidos nem duplicatas.",
    )
