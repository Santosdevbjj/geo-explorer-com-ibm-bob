"""Ferramentas MCP somente leitura do Sentinel.

As funções não aceitam caminhos do cliente, não executam comandos e não registram
payloads brutos. A validação de eventos usa o schema Pydantic do próprio produto.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_EVENT_BYTES = 16_384
ROOT = Path(__file__).resolve().parents[1]


def get_model_info() -> dict[str, Any]:
    """Retorna versão e disponibilidade do modelo, sem expor artefatos."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from sentinel.config import settings
    from sentinel.detection.model import get_detector

    detector = get_detector()
    loaded = bool(detector.is_fitted)
    return {
        "service": "sentinel",
        "model_version": settings.model_version,
        "algorithm": "IsolationForest",
        "model_loaded": loaded,
        "inference_mode": "rules-only",
        "model_inference_status": "loaded_not_used_for_alert_scoring"
        if loaded
        else "not_loaded",
        "score_is_calibrated_probability": False,
        "limitations": [
            "O modelo é um baseline experimental e ainda não compõe o score final dos alertas.",
            "Modelo treinado com dados sintéticos até que haja dataset autorizado e rotulado.",
            "Score de anomalia não é probabilidade calibrada.",
        ],
    }


def analyze_event(event: dict[str, Any]) -> dict[str, Any]:
    """Valida e analisa um evento; retorna apenas resumo e sinais, não o payload."""
    if not isinstance(event, dict):
        raise ValueError("event deve ser um objeto JSON.")
    encoded = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    if len(encoded) > MAX_EVENT_BYTES:
        raise ValueError(f"Evento excede o limite de {MAX_EVENT_BYTES} bytes.")

    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from pydantic import ValidationError

    from sentinel.detection.rules import apply_rules
    from sentinel.detection.scoring import score_matches
    from sentinel.schemas import LogEvent

    try:
        parsed = LogEvent.model_validate(event)
    except ValidationError as exc:
        # Retorna campos/erros de schema, nunca inclui valores de entrada no resultado.
        issues = [
            {"field": ".".join(str(part) for part in item["loc"]), "type": item["type"]}
            for item in exc.errors()
        ]
        return {"valid": False, "issues": issues}

    matches = apply_rules([parsed])
    alert = score_matches(matches, model_version="rules-only")
    if alert is None:
        return {
            "valid": True,
            "alert_generated": False,
            "signals": [],
            "note": "Nenhuma regra disparou; isso não comprova ausência de ameaça.",
        }
    return {
        "valid": True,
        "alert_generated": True,
        "alert": {
            "alert_id": alert.alert_id,
            "category": str(alert.category),
            "priority": str(alert.priority),
            "score": alert.score,
            "score_is_calibrated_probability": False,
            "signals": [
                {
                    "name": signal.name,
                    "source": str(signal.source),
                    "contribution": signal.contribution,
                }
                for signal in alert.signals
            ],
            "limitations": alert.limitations,
        },
    }


def get_metrics_summary() -> dict[str, Any]:
    """Lê somente um relatório fixo de avaliação, selecionando métricas conhecidas."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from sentinel.config import settings

    path = ROOT / "reports" / f"evaluation_{settings.model_version}.json"
    if not path.is_file():
        return {
            "available": False,
            "model_version": settings.model_version,
            "message": "Relatório de avaliação ainda não foi gerado.",
        }
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "message": "Relatório de avaliação indisponível ou inválido.",
        }

    allowed = (
        "precision",
        "recall",
        "f1",
        "f1_score",
        "pr_auc",
        "roc_auc",
        "false_positive_rate",
        "fpr",
        "n_samples",
        "n_test_samples",
        "model_version",
        "evaluated_at",
        "disclaimer",
    )
    summary = {
        key: report[key]
        for key in allowed
        if key in report
        and isinstance(report[key], (str, int, float, bool, type(None)))
    }
    summary.setdefault(
        "disclaimer", "Métricas de dados sintéticos não representam desempenho real."
    )
    return {"available": True, "summary": summary}


def get_drift_summary() -> dict[str, Any]:
    """Lê um resumo de drift fixo; não permite que o cliente escolha um arquivo."""
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from sentinel.config import settings

    path = ROOT / "reports" / f"drift_{settings.model_version}.json"
    if not path.is_file():
        return {
            "available": False,
            "model_version": settings.model_version,
            "message": "Resumo de drift ainda não foi persistido.",
            "interpretation": (
                "Data drift descreve mudança nas entradas; sozinho não prova perda de acurácia. "
                "Concept drift exige rótulos/resultados posteriores para avaliar a relação entrada-alvo."
            ),
        }
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "available": False,
            "message": "Relatório de drift indisponível ou inválido.",
        }

    # Resumo permitido: sem linhas de eventos ou dados brutos.
    return {
        "available": True,
        "model_version": settings.model_version,
        "drift_detected": bool(report.get("drift_detected", False)),
        "threshold": report.get("threshold"),
        "n_current_samples": report.get("n_current_samples"),
        "n_reference_samples": report.get("n_reference_samples"),
        "message": str(report.get("message", ""))[:500],
        "interpretation": (
            "Data drift não equivale automaticamente à queda de desempenho. "
            "Verifique rótulos posteriores e métricas por janela."
        ),
    }
