"""Script de treinamento do modelo de detecção de anomalias do Sentinel.

Registra: seed, dependências, configuração, features utilizadas, hash do dataset
e metadados completos do treino em models/metadata_<version>.json.

Fluxo:
    1. Carrega e valida o dataset JSONL
    2. Computa hash SHA-256 do dataset (reprodutibilidade)
    3. Divide temporalmente: treino (1 - test_split) / teste (test_split)
    4. Extrai features (sem usar metadata.label — sem vazamento)
    5. Treina AnomalyDetector (IsolationForest + StandardScaler)
    6. Salva artefatos .joblib + distribuição de referência para drift
    7. Salva metadados completos em JSON

Uso:
    python scripts/train_model.py
    python scripts/train_model.py --input data/synthetic/events.jsonl --version v2
    python scripts/train_model.py --n-estimators 200 --contamination 0.05

AVISO: Modelo treinado em dados sintéticos.
Scores NÃO são probabilidades calibradas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _sha256_file(path: Path) -> str:
    """Calcula hash SHA-256 do arquivo para rastreabilidade do dataset."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_events_jsonl(path: Path) -> list[dict]:
    """Carrega eventos de um arquivo JSONL, descartando linhas malformadas."""
    events = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Linha %d — JSON inválido ignorado: %s", lineno, exc)
    return events


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Treina o AnomalyDetector do Sentinel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "AVISO: modelo treinado em dados sintéticos.\n"
            "Scores NÃO são probabilidades calibradas.\n"
            "Execute evaluate_model.py para ver métricas de comparação com baseline."
        ),
    )
    parser.add_argument("--input", default="data/synthetic/events.jsonl")
    parser.add_argument("--output-dir", default="models")
    parser.add_argument("--version", default=None, help="Versão do modelo (padrão: MODEL_VERSION do .env)")
    parser.add_argument("--test-split", type=float, default=0.20,
                        help="Proporção temporal de teste (padrão: 0.20)")
    parser.add_argument("--contamination", type=float, default=None,
                        help="Proporção de anomalias estimada para IsolationForest (padrão: MODEL_CONTAMINATION)")
    parser.add_argument("--n-estimators", type=int, default=None,
                        help="Número de árvores (padrão: MODEL_N_ESTIMATORS)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed para reprodutibilidade (padrão: MODEL_RANDOM_STATE)")
    parser.add_argument("--window-seconds", type=int, default=300,
                        help="Janela de features em segundos (padrão: 300)")
    args = parser.parse_args()

    # ── Importações tardias ────────────────────────────────────────────────
    from pydantic import ValidationError

    from sentinel.config import settings
    from sentinel.data.validation import validate_batch
    from sentinel.detection.model import FEATURE_COLUMNS, AnomalyDetector
    from sentinel.features.engineering import (
        FEATURE_COLUMNS as ENG_FEATURE_COLUMNS,
        extract_features,
    )
    from sentinel.schemas import LogEvent

    # Override de configuração via argparse
    if args.version:
        settings.model_version = args.version  # type: ignore[misc]
    contamination = args.contamination or settings.model_contamination
    n_estimators = args.n_estimators or settings.model_n_estimators
    random_state = args.seed if args.seed is not None else settings.model_random_state

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Arquivo não encontrado: %s", input_path)
        logger.error("Execute antes: python scripts/generate_synthetic_data.py")
        sys.exit(1)

    # ── Hash do dataset (rastreabilidade) ─────────────────────────────────
    dataset_hash = _sha256_file(input_path)
    logger.info("Dataset: %s (SHA-256: %s...)", input_path, dataset_hash[:12])

    # ── Carregamento e validação ───────────────────────────────────────────
    logger.info("Carregando dados de: %s", input_path)
    raw_records = _load_events_jsonl(input_path)
    logger.info("Total de registros carregados: %d", len(raw_records))

    report = validate_batch(raw_records)
    logger.info(
        "Validação: %d válidos / %d inválidos / %d duplicatas",
        report.valid_records,
        report.invalid_records,
        len(report.duplicate_ids),
    )

    # Filtra apenas registros válidos (Pydantic)
    # metadata.label NÃO é usado aqui — só para avaliação posterior
    valid_events: list[LogEvent] = []
    for raw in raw_records:
        if raw.get("metadata", {}).get("label") == "invalid":
            continue  # registros inválidos injetados para testes de validação
        try:
            valid_events.append(LogEvent.model_validate(raw))
        except ValidationError:
            continue

    logger.info("Eventos válidos para treino/teste: %d", len(valid_events))

    if len(valid_events) < 50:
        logger.error("Dados insuficientes (mínimo: 50). Encontrado: %d", len(valid_events))
        sys.exit(1)

    # ── Divisão temporal treino/teste ─────────────────────────────────────
    # Divisão temporal evita vazamento: eventos mais recentes são avaliados em holdout
    valid_events_sorted = sorted(valid_events, key=lambda e: e.timestamp)
    n_test = max(1, int(len(valid_events_sorted) * args.test_split))
    train_events = valid_events_sorted[:-n_test]
    test_events = valid_events_sorted[-n_test:]
    logger.info(
        "Divisão temporal: %d treino / %d teste (%.0f%% / %.0f%%)",
        len(train_events), len(test_events),
        (1 - args.test_split) * 100, args.test_split * 100,
    )

    if len(train_events) < 30:
        logger.error("Treino insuficiente após divisão: %d eventos", len(train_events))
        sys.exit(1)

    # ── Engenharia de features (SEM metadata.label) ────────────────────────
    logger.info("Extraindo features de treino (window=%ds)...", args.window_seconds)
    features_train = extract_features(train_events, window_seconds=args.window_seconds)
    logger.info(
        "Features de treino: %d linhas × %d features",
        len(features_train), len(FEATURE_COLUMNS),
    )

    if len(features_train) == 0:
        logger.error("Nenhuma feature extraída. Verifique os dados de entrada.")
        sys.exit(1)

    # Verifica consistência de features entre engineering e model
    missing_features = [c for c in FEATURE_COLUMNS if c not in features_train.columns]
    if missing_features:
        logger.error(
            "Features esperadas pelo modelo ausentes no DataFrame: %s\n"
            "Verifique se engineering.FEATURE_COLUMNS está sincronizado com model.FEATURE_COLUMNS.",
            missing_features,
        )
        sys.exit(1)

    # ── Treino ─────────────────────────────────────────────────────────────
    logger.info(
        "Treinando AnomalyDetector (contamination=%.3f, n_estimators=%d, seed=%d)...",
        contamination, n_estimators, random_state,
    )
    detector = AnomalyDetector(
        contamination=contamination,
        n_estimators=n_estimators,
        random_state=random_state,
    )
    detector.fit(features_train)

    # ── Persistência ──────────────────────────────────────────────────────
    output_dir = Path(args.output_dir)
    saved = detector.save(output_dir)
    logger.info("Artefatos salvos: %s", saved)

    # ── Distribuição de referência para drift ─────────────────────────────
    processed_dir = Path(settings.data_processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    ref_path = processed_dir / "reference_distribution.json"
    features_train[FEATURE_COLUMNS].to_json(ref_path, orient="records", indent=2)
    logger.info("Distribuição de referência salva: %s", ref_path)

    # ── Dependências e versões ─────────────────────────────────────────────
    import importlib
    dep_versions: dict[str, str] = {}
    for pkg in ("numpy", "pandas", "sklearn", "joblib", "pydantic"):
        try:
            mod = importlib.import_module(pkg if pkg != "sklearn" else "sklearn")
            dep_versions[pkg] = getattr(mod, "__version__", "unknown")
        except ImportError:
            dep_versions[pkg] = "not_installed"

    # ── Metadados completos do treino ─────────────────────────────────────
    metadata: dict = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.model_version,
        "algorithm": "IsolationForest + StandardScaler",
        # Configuração
        "config": {
            "contamination": contamination,
            "n_estimators": n_estimators,
            "random_state": random_state,
            "window_seconds": args.window_seconds,
            "test_split": args.test_split,
        },
        # Dataset
        "dataset": {
            "input_file": str(input_path),
            "sha256": dataset_hash,
            "total_records": len(raw_records),
            "valid_events": len(valid_events),
            "n_train_events": len(train_events),
            "n_test_events": len(test_events),
            "n_train_feature_rows": len(features_train),
        },
        # Features usadas
        "feature_columns": FEATURE_COLUMNS,
        "engineering_feature_columns": ENG_FEATURE_COLUMNS,
        # Dependências
        "dependencies": dep_versions,
        # Artefatos
        "artifacts": {k: str(v) for k, v in saved.items()},
        "reference_distribution": str(ref_path),
        # Avisos
        "warnings": [
            "Modelo treinado em dados sintéticos — não generaliza para dados reais sem validação.",
            "Scores NÃO são probabilidades calibradas.",
            "Execute evaluate_model.py para métricas de comparação com baseline.",
        ],
    }

    meta_path = output_dir / f"metadata_{settings.model_version}.json"
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    logger.info("Metadados salvos: %s", meta_path)

    logger.info(
        "Treino concluído — versão %s | %d features | dataset SHA-256: %s...",
        settings.model_version, len(FEATURE_COLUMNS), dataset_hash[:12],
    )
    logger.info("Execute: python scripts/evaluate_model.py --model-dir %s", args.output_dir)


if __name__ == "__main__":
    main()
