"""API FastAPI do Sentinel — camada de transporte HTTP.

Esta camada NÃO contém lógica analítica.
Toda lógica de detecção e validação está em src/sentinel/.

Endpoints:
    GET  /health           → verificação de saúde
    POST /ingest           → valida um batch de eventos
    POST /detect           → executa detecção e retorna alertas
    GET  /alerts/{alert_id} → recupera um alerta por ID (in-memory, dev only)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sentinel.config import settings
from sentinel.data.validation import validate_batch
from sentinel.detection.model import get_detector
from sentinel.detection.rules import apply_rules
from sentinel.detection.scoring import score_matches
from sentinel.schemas import Alert, LogEvent, ValidationReport

logger = logging.getLogger(__name__)
MAX_EVENT_BYTES = 65_536


def _enforce_event_size(events: list[dict[str, Any]]) -> None:
    """Limita o tamanho serializado de cada evento sem registrar seu conteúdo."""
    import json

    for index, event in enumerate(events):
        try:
            size = len(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Evento na posição {index} não pode ser serializado como JSON.",
            ) from None
        if size > MAX_EVENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Evento na posição {index} excede o limite de {MAX_EVENT_BYTES} bytes.",
            )


# ── Autenticação (ADR-005) ─────────────────────────────────────────────────


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Valida o header X-Api-Key contra API_SECRET_KEY do .env.

    Endpoints públicos: /health, /alerts (GET), /metrics
    Endpoints protegidos: /ingest, /detect
    """
    expected = settings.api_secret_key
    if expected == "change-me-in-production":
        # Fail closed em produção: não aceite a chave placeholder.
        if settings.sentinel_env.lower() == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API_SECRET_KEY precisa ser configurada no ambiente de produção.",
            )
        # Em desenvolvimento/testes, a autenticação pode ficar desabilitada.
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou ausente. Inclua o header X-Api-Key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# ── Lifespan (startup: carrega modelo) ────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    # Startup: tenta carregar modelo do disco (fallback rules-only se ausente)
    get_detector()
    yield
    # Shutdown: sem recursos para liberar


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    lifespan=lifespan,
    title="Intelligent DevSecOps Sentinel",
    description=(
        "Pipeline analítico de segurança: ingestão, validação, detecção baseada em "
        "regras, priorização com explicabilidade e monitoramento de modelos."
    ),
    version="0.1.0",
    contact={
        "name": "Sergio Santos",
        "url": "https://github.com/Santosdevbjj/geo-explorer-com-ibm-bob",
    },
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────

_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Api-Key"],
)

# Armazenamento em memória para desenvolvimento
_alert_store: dict[str, Alert] = {}


# ── Schemas de request/response ────────────────────────────────────────────


class IngestRequest(BaseModel):
    """Corpo da requisição de ingestão de eventos."""

    events: list[dict[str, Any]] = Field(
        min_length=1,
        description="Lista de eventos de log em formato dicionário.",
        examples=[
            [
                {
                    "timestamp": "2025-01-15T14:23:00Z",
                    "source_ip": "192.168.1.10",
                    "event_type": "auth_attempt",
                    "status": "failure",
                }
            ]
        ],
    )


class DetectRequest(BaseModel):
    """Corpo da requisição de detecção."""

    events: list[dict[str, Any]] = Field(
        min_length=1,
        description="Lista de eventos a analisar.",
    )
    validate_first: bool = Field(
        default=True,
        description="Se True, valida o schema antes de detectar. Recomendado.",
    )


class DetectResponse(BaseModel):
    """Resposta da detecção com alertas gerados."""

    alerts_generated: int
    alerts: list[Alert]
    validation_summary: dict[str, Any] | None = None


class AnalyzeBatchRequest(BaseModel):
    """Eventos tipados para análise em lote."""

    model_config = {"extra": "forbid"}
    events: list[LogEvent] = Field(min_length=1, description="Eventos a analisar.")


class ModelInfoResponse(BaseModel):
    """Estado operacional do modelo, separado da saúde da API."""

    service: str = "sentinel"
    model_version: str
    algorithm: str = "IsolationForest"
    model_loaded: bool
    inference_mode: str
    model_inference_status: str
    score_is_calibrated_probability: bool = False
    limitations: list[str] = Field(default_factory=list)


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get(
    "/health",
    summary="Health check",
    tags=["infra"],
    response_description="Status da aplicação",
)
def health() -> dict[str, str]:
    """Verifica se a API está operacional."""
    return {"status": "ok", "service": "sentinel", "version": "0.1.0"}


@app.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Informações operacionais do modelo",
    tags=["infra", "modelo"],
)
def model_info() -> ModelInfoResponse:
    """Informa se o modelo foi carregado; não confunde saúde da API com saúde do modelo."""
    detector = get_detector()
    loaded = bool(detector.is_fitted)
    return ModelInfoResponse(
        model_version=settings.model_version,
        model_loaded=loaded,
        # O artefato pode ser carregado, mas o score ainda não participa do scoring de alertas.
        inference_mode="rules-only",
        model_inference_status=(
            "loaded_not_used_for_alert_scoring" if loaded else "not_loaded"
        ),
        limitations=[
            "O modelo está disponível como baseline experimental, mas ainda não compõe o score final dos alertas.",
            "O score de anomalia não é uma probabilidade calibrada.",
            "A ausência do artefato de ML não torna a API indisponível; regras continuam disponíveis.",
        ],
    )


@app.post(
    "/analyze",
    response_model=DetectResponse,
    summary="Analisar um evento",
    tags=["pipeline"],
)
def analyze(
    body: LogEvent,
    _auth: None = Depends(require_api_key),
) -> DetectResponse:
    """Analisa um evento tipado; nunca aceita caminhos ou código fornecidos pelo cliente."""
    return detect(
        DetectRequest(events=[body.model_dump(mode="json")], validate_first=True),
        _auth=None,
    )


@app.post(
    "/analyze/batch",
    response_model=DetectResponse,
    summary="Analisar um lote de eventos",
    tags=["pipeline"],
)
def analyze_batch(
    body: AnalyzeBatchRequest,
    _auth: None = Depends(require_api_key),
) -> DetectResponse:
    """Analisa um lote limitado, validado por Pydantic, sem aceitar caminhos arbitrários."""
    if len(body.events) > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch excede o limite de {settings.max_batch_size} eventos.",
        )
    events = [event.model_dump(mode="json") for event in body.events]
    return detect(DetectRequest(events=events, validate_first=True), _auth=None)


@app.post(
    "/ingest",
    response_model=ValidationReport,
    status_code=status.HTTP_200_OK,
    summary="Ingerir e validar eventos",
    tags=["pipeline"],
    response_description="Relatório de validação do batch",
)
def ingest(
    body: IngestRequest,
    _auth: None = Depends(require_api_key),
) -> ValidationReport:
    """Recebe um batch de eventos, valida o schema e retorna o relatório.

    - Detecta campos obrigatórios ausentes
    - Identifica tipos inválidos (IP, porta, timestamp sem timezone)
    - Relata event_ids duplicados
    - Retorna HTTP 200 com o relatório (mesmo em caso de registros inválidos)
    - Requer header X-Api-Key (quando API_SECRET_KEY configurada)
    - Limite máximo: MAX_BATCH_SIZE eventos por requisição
    """
    if len(body.events) > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch excede o limite de {settings.max_batch_size} eventos.",
        )
    _enforce_event_size(body.events)
    report = validate_batch(body.events)
    logger.info(
        "/ingest: %d registros, %d válidos, %d inválidos",
        report.total_records,
        report.valid_records,
        report.invalid_records,
    )
    return report


@app.post(
    "/detect",
    response_model=DetectResponse,
    status_code=status.HTTP_200_OK,
    summary="Detectar comportamentos suspeitos",
    tags=["pipeline"],
    response_description="Alertas gerados com prioridade e sinais de explicabilidade",
)
def detect(
    body: DetectRequest,
    _auth: None = Depends(require_api_key),
) -> DetectResponse:
    """Executa o pipeline de detecção sobre um batch de eventos.

    Pipeline:
    1. (Opcional) Valida schema dos eventos
    2. Converte dicionários em objetos LogEvent
    3. Aplica regras de detecção (brute force, traffic spike, injection)
    4. Pontua e prioriza matches em alertas explicáveis
    5. Armazena alertas em memória para consulta via GET /alerts/{id}

    **Importante:** O score do alerta não é uma probabilidade calibrada.
    """
    if len(body.events) > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch excede o limite de {settings.max_batch_size} eventos.",
        )
    _enforce_event_size(body.events)
    validation_summary = None

    # Passo 1: validação opcional
    if body.validate_first:
        report = validate_batch(body.events)
        validation_summary = {
            "total": report.total_records,
            "valid": report.valid_records,
            "invalid": report.invalid_records,
            "passed": report.passed,
        }
        if not report.passed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Batch contém registros inválidos. Execute /ingest para detalhes.",
                    "invalid_count": report.invalid_records,
                    "duplicate_count": len(report.duplicate_ids),
                },
            )

    # Passo 2: deserialização (registros já validados pelo Pydantic acima)
    from pydantic import ValidationError

    parsed_events: list[LogEvent] = []
    for raw in body.events:
        try:
            parsed_events.append(LogEvent.model_validate(raw))
        except ValidationError:
            continue  # ignora silenciosamente (já tratado acima se validate_first=True)

    if not parsed_events:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum evento válido para processar.",
        )

    # Passo 3–4: detecção, scoring (regras + modelo ML se disponível)
    # Nesta versão, o score final do alerta é baseado em regras explícitas.
    # O modelo existe como baseline experimental, mas ainda não está integrado ao scoring.
    matches = apply_rules(parsed_events)
    model_version = "rules-only"
    alert = score_matches(matches, model_version=model_version)

    alerts: list[Alert] = []
    if alert is not None:
        _alert_store[alert.alert_id] = alert
        alerts.append(alert)

    logger.info(
        "/detect: %d eventos → %d matches → %d alertas",
        len(parsed_events),
        len(matches),
        len(alerts),
    )

    return DetectResponse(
        alerts_generated=len(alerts),
        alerts=alerts,
        validation_summary=validation_summary,
    )


@app.get(
    "/alerts/{alert_id}",
    response_model=Alert,
    status_code=status.HTTP_200_OK,
    summary="Recuperar alerta por ID",
    tags=["alertas"],
    response_description="Alerta com sinais e limitações",
)
def get_alert(alert_id: str) -> Alert:
    """Retorna um alerta específico pelo seu ID.

    **Nota:** Este endpoint usa armazenamento em memória (desenvolvimento).
    Os alertas são perdidos ao reiniciar a aplicação.
    """
    alert = _alert_store.get(alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerta '{alert_id}' não encontrado.",
        )
    return alert


@app.get(
    "/alerts",
    response_model=list[Alert],
    status_code=status.HTTP_200_OK,
    summary="Listar todos os alertas",
    tags=["alertas"],
)
def list_alerts() -> list[Alert]:
    """Lista todos os alertas armazenados em memória (desenvolvimento)."""
    return list(_alert_store.values())


@app.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Métricas do modelo e status de drift",
    tags=["avaliação"],
    response_description="Último relatório de avaliação salvo em reports/",
)
def get_metrics() -> dict:
    """Retorna o último relatório de avaliação do modelo, se disponível.

    O relatório é gerado por `scripts/evaluate_model.py` e salvo em `reports/`.
    Endpoint somente leitura — não recalcula métricas em tempo real.

    Inclui campo `disclaimer` explícito sobre as limitações das métricas.
    """
    import json as _json
    from pathlib import Path as _Path

    from sentinel.config import settings as _settings
    from sentinel.detection.model import get_detector as _get_detector

    report_path = _Path("reports") / f"evaluation_{_settings.model_version}.json"

    evaluation: dict = {}
    if report_path.exists():
        try:
            with report_path.open(encoding="utf-8") as f:
                evaluation = _json.load(f)
        except Exception:  # noqa: BLE001
            evaluation = {"error": "Relatório de avaliação corrompido."}
    else:
        evaluation = {
            "message": (
                f"Relatório não encontrado em '{report_path}'. "
                "Execute scripts/evaluate_model.py para gerar."
            )
        }

    detector = _get_detector()
    return {
        "model_version": _settings.model_version,
        "model_loaded": detector.is_fitted,
        "evaluation": evaluation,
    }
