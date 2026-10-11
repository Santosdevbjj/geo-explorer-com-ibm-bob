"""Validação de qualidade de dados do Sentinel.

Responsabilidades:
- Validar schema de cada registro (via Pydantic)
- Detectar campos obrigatórios ausentes
- Identificar registros duplicados por event_id
- Retornar ValidationReport estruturado (nunca descartar silenciosamente)
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from sentinel.schemas import (
    AlertCategory,
    FieldError,
    InvalidRecord,
    LogEvent,
    ValidationReport,
)

logger = logging.getLogger(__name__)


def validate_batch(records: list[dict[str, Any]]) -> ValidationReport:
    """Valida um batch de eventos de log brutos.

    Args:
        records: Lista de dicionários representando eventos de log.

    Returns:
        ValidationReport com contagens, duplicatas e detalhes de erros.
        Nunca levanta exceção — erros são capturados e relatados no report.
    """
    valid_count = 0
    invalid_details: list[InvalidRecord] = []
    seen_ids: dict[str, int] = {}  # event_id → primeira ocorrência (índice)
    duplicate_ids: list[str] = []
    missing_fields_summary: dict[str, int] = {}

    for idx, raw in enumerate(records):
        # ── Validação de schema via Pydantic ──────────────────────────────
        field_errors: list[FieldError] = []
        event_id: str | None = raw.get("event_id")

        try:
            event = LogEvent.model_validate(raw)
            event_id = event.event_id
        except ValidationError as exc:
            for err in exc.errors():
                field_name = ".".join(str(loc) for loc in err["loc"])
                field_errors.append(
                    FieldError(
                        field=field_name,
                        error=err["msg"],
                        value=err.get("input"),
                    )
                )
                missing_fields_summary[field_name] = (
                    missing_fields_summary.get(field_name, 0) + 1
                )

        if field_errors:
            invalid_details.append(
                InvalidRecord(
                    record_index=idx,
                    event_id=event_id,
                    errors=field_errors,
                )
            )
            logger.debug("Registro %d inválido: %d erro(s)", idx, len(field_errors))
            continue

        # ── Detecção de duplicatas por event_id ───────────────────────────
        if event_id in seen_ids:
            if event_id not in duplicate_ids:
                duplicate_ids.append(event_id)
            logger.debug("event_id duplicado: %s (índices %d e %d)", event_id, seen_ids[event_id], idx)
        else:
            seen_ids[event_id] = idx

        valid_count += 1

    total = len(records)
    invalid_count = len(invalid_details)

    report = ValidationReport(
        total_records=total,
        valid_records=valid_count,
        invalid_records=invalid_count,
        duplicate_ids=duplicate_ids,
        missing_fields_summary=missing_fields_summary,
        invalid_record_details=invalid_details,
        passed=(invalid_count == 0 and len(duplicate_ids) == 0),
    )

    logger.info(
        "Validação concluída: %d/%d válidos, %d inválidos, %d duplicatas",
        valid_count,
        total,
        invalid_count,
        len(duplicate_ids),
    )
    return report


# Mantém compatibilidade — utilidade para categoria de alertas futura
__all__ = ["validate_batch", "AlertCategory"]
