"""CLI de validação de batch de eventos do Sentinel.

Lê um arquivo JSONL, executa validate_batch() e imprime o relatório.
Sai com código 1 se a validação não passar.

Uso:
    python scripts/validate_data.py --input data/synthetic/events.jsonl
    python scripts/validate_data.py --input data/raw/logs.jsonl --strict
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_jsonl(path: Path) -> list[dict]:
    """Carrega um arquivo JSONL linha a linha."""
    records = []
    errors = 0
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Linha %d — JSON inválido: %s", lineno, exc)
                errors += 1
    if errors:
        logger.warning("%d linha(s) com JSON inválido ignorada(s)", errors)
    return records


def print_report(report) -> None:  # type: ignore[no-untyped-def]
    """Imprime o ValidationReport formatado no stdout."""
    print("\n" + "=" * 60)
    print("SENTINEL — RELATÓRIO DE VALIDAÇÃO")
    print("=" * 60)
    print(f"  Total de registros : {report.total_records}")
    print(f"  Válidos            : {report.valid_records}")
    print(f"  Inválidos          : {report.invalid_records}")
    print(f"  IDs duplicados     : {len(report.duplicate_ids)}")
    print(f"  Resultado          : {'✅ PASSOU' if report.passed else '❌ FALHOU'}")

    if report.missing_fields_summary:
        print("\n  Campos com erros (contagem):")
        for field, count in sorted(report.missing_fields_summary.items()):
            print(f"    • {field}: {count}")

    if report.duplicate_ids:
        print(f"\n  IDs duplicados ({len(report.duplicate_ids)}):")
        for eid in report.duplicate_ids[:10]:
            print(f"    • {eid}")
        if len(report.duplicate_ids) > 10:
            print(f"    ... e mais {len(report.duplicate_ids) - 10}")

    if report.invalid_record_details:
        shown = report.invalid_record_details[:5]
        print(f"\n  Detalhes dos primeiros {len(shown)} registro(s) inválido(s):")
        for rec in shown:
            print(f"    [idx={rec.record_index}] event_id={rec.event_id}")
            for err in rec.errors:
                print(f"      campo '{err.field}': {err.error}")
        if len(report.invalid_record_details) > 5:
            remaining = len(report.invalid_record_details) - 5
            print(f"    ... e mais {remaining} registro(s) inválido(s)")

    print("=" * 60 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validador de batch de eventos do Sentinel"
    )
    parser.add_argument(
        "--input", required=True, help="Caminho do arquivo JSONL a validar"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Sai com código 1 mesmo se houver apenas duplicatas (sem erros de schema)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Arquivo não encontrado: %s", input_path)
        sys.exit(1)

    logger.info("Carregando: %s", input_path)
    records = load_jsonl(input_path)

    if not records:
        logger.error("Nenhum registro carregado de %s", input_path)
        sys.exit(1)

    # Importação tardia para não forçar dependências do pacote no script CLI
    from sentinel.data.validation import validate_batch

    report = validate_batch(records)
    print_report(report)

    if not report.passed:
        sys.exit(1)

    if args.strict and report.duplicate_ids:
        logger.warning(
            "Modo --strict: %d duplicata(s) encontrada(s)", len(report.duplicate_ids)
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
