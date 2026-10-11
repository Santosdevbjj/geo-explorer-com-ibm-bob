"""Script de avaliação do modelo de detecção do Sentinel.

Compara o IsolationForest com duas baselines determinísticas:
  1. majority_class  : prediz sempre "normal" (0) — útil quando anomalias são raras
  2. rule_based      : pipeline de regras explícitas já implementado (BruteForce + TrafficSpike + Injection)

Calcula: precision, recall, F1 macro, PR-AUC, matriz de confusão, FPR por detector.
Limiar de binarização (threshold) é ajustado SOMENTE em validação — nunca no teste.
Salva relatório em reports/evaluation_<version>.json.

AVISO: Métricas calculadas sobre dados SINTÉTICOS com rótulos simulados.
Não generalizam para dados reais sem validação adicional.
Scores NÃO são probabilidades calibradas.

Uso:
    python scripts/evaluate_model.py
    python scripts/evaluate_model.py --input data/synthetic/events.jsonl
    python scripts/evaluate_model.py --threshold 0.4 --no-model
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Avalia e compara detectores do Sentinel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "AVISO: métricas sobre dados sintéticos.\n"
            "Scores NÃO são probabilidades calibradas.\n"
            "FPR alto sobrecarrega analistas com alertas falsos."
        ),
    )
    parser.add_argument("--input", default="data/synthetic/events.jsonl")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument(
        "--test-split", type=float, default=0.20,
        help="Proporção temporal de teste (deve ser igual ao treino, padrão: 0.20)",
    )
    parser.add_argument(
        "--val-split", type=float, default=0.10,
        help="Proporção de validação (do treino) para ajuste de threshold (padrão: 0.10)",
    )
    parser.add_argument(
        "--threshold", type=float, default=None,
        help="Threshold fixo para binarização do score. Se omitido, ajustado em validação.",
    )
    parser.add_argument(
        "--window-seconds", type=int, default=300,
        help="Janela de features (deve ser igual ao treino, padrão: 300)",
    )
    parser.add_argument(
        "--no-model", action="store_true",
        help="Avalia apenas as baselines sem tentar carregar o modelo ML",
    )
    args = parser.parse_args()

    # ── Importações tardias ────────────────────────────────────────────────
    import numpy as np
    from pydantic import ValidationError

    from sentinel.config import settings
    from sentinel.detection.rules import apply_rules
    from sentinel.evaluation.metrics import (
        ComparisonReport,
        MetricsReport,
        compare_detectors,
        compute_metrics,
        compute_pr_auc,
    )
    from sentinel.features.engineering import extract_features
    from sentinel.schemas import LogEvent

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("Arquivo não encontrado: %s", input_path)
        sys.exit(1)

    # ── Carregamento ───────────────────────────────────────────────────────
    with input_path.open(encoding="utf-8") as f:
        raw_records = [json.loads(line) for line in f if line.strip()]

    # Converte para LogEvent excluindo inválidos injetados para testes
    valid_events: list[LogEvent] = []
    labels_all: list[str] = []
    for raw in raw_records:
        label = raw.get("metadata", {}).get("label", "normal")
        if label == "invalid":
            continue
        try:
            valid_events.append(LogEvent.model_validate(raw))
            labels_all.append(label)
        except ValidationError:
            continue

    # ── Divisão temporal: treino / validação / teste ──────────────────────
    # Mantém a mesma divisão do train_model.py para evitar vazamento
    n_total = len(valid_events)
    sorted_indices = sorted(range(n_total), key=lambda i: valid_events[i].timestamp)
    valid_events_sorted = [valid_events[i] for i in sorted_indices]
    labels_sorted = [labels_all[i] for i in sorted_indices]

    n_test = max(1, int(n_total * args.test_split))
    n_val = max(1, int((n_total - n_test) * args.val_split))

    train_events = valid_events_sorted[:-(n_test + n_val)]
    val_events   = valid_events_sorted[-(n_test + n_val):-n_test]
    test_events  = valid_events_sorted[-n_test:]
    val_labels   = labels_sorted[-(n_test + n_val):-n_test]
    test_labels  = labels_sorted[-n_test:]

    logger.info(
        "Divisão temporal: %d treino / %d validação / %d teste",
        len(train_events), len(val_events), len(test_events),
    )

    # ── Rótulos binários (0=normal, 1=anomalia) ───────────────────────────
    # metadata.label é usado APENAS aqui (avaliação), nunca no treino de features
    def _to_binary(labels: list[str]) -> np.ndarray:
        return np.array([0 if lb == "normal" else 1 for lb in labels])

    y_val  = _to_binary(val_labels)
    y_test = _to_binary(test_labels)

    n_pos_test = int(y_test.sum())
    n_neg_test = int((y_test == 0).sum())
    logger.info(
        "Teste: %d anomalias / %d normais (%.1f%% anomaly rate)",
        n_pos_test, n_neg_test,
        100 * n_pos_test / max(len(y_test), 1),
    )

    if n_pos_test == 0:
        logger.warning(
            "Nenhuma anomalia no conjunto de teste. "
            "Métricas de detecção (recall, F1 da classe anomaly) não são calculáveis. "
            "Use --test-split maior ou gere dados com maior --anomaly-rate."
        )

    # ── Features ─────────────────────────────────────────────────────────
    features_val  = extract_features(val_events,  window_seconds=args.window_seconds)
    features_test = extract_features(test_events, window_seconds=args.window_seconds)

    # ── Baseline 1: majority_class (prediz sempre normal) ─────────────────
    y_pred_majority = np.zeros(len(test_events), dtype=int)
    report_majority = compute_metrics(y_test, y_pred_majority, "majority_class_baseline")
    logger.info(
        "Baseline majority_class — F1 macro: %s | FPR: %s",
        report_majority.macro_f1, report_majority.false_positive_rate,
    )

    # ── Baseline 2: rule_based ─────────────────────────────────────────────
    rule_matches = apply_rules(test_events)
    detected_ids: set[str] = set()
    for match in rule_matches:
        detected_ids.update(match.matched_event_ids)
    y_pred_rules = np.array([
        1 if e.event_id in detected_ids else 0
        for e in test_events
    ])
    report_rules = compute_metrics(y_test, y_pred_rules, "rule_based_baseline")
    logger.info(
        "Baseline rule_based — F1 macro: %s | recall: %s | FPR: %s",
        report_rules.macro_f1,
        next((pc.recall for pc in report_rules.per_class if pc.label == "anomaly"), None),
        report_rules.false_positive_rate,
    )

    # ── Modelo ML (IsolationForest) — opcional ────────────────────────────
    report_model: MetricsReport | None = None
    comparison_vs_majority: ComparisonReport | None = None
    comparison_vs_rules: ComparisonReport | None = None
    threshold_used: float | None = None

    if not args.no_model:
        try:
            from sentinel.detection.model import AnomalyDetector
            detector = AnomalyDetector.load(args.model_dir)

            # Ajuste de threshold em VALIDAÇÃO (nunca no teste)
            if args.threshold is not None:
                threshold_used = args.threshold
                logger.info("Threshold fixo: %.3f (fornecido via --threshold)", threshold_used)
            elif len(features_val) > 0 and n_pos_test > 0:
                scores_val = detector.predict(features_val)
                # Alinha scores de validação com eventos de validação por source_ip
                event_scores_val = _align_scores_to_events(val_events, features_val, scores_val)
                # Busca threshold que maximiza F1 da classe anomaly em validação
                threshold_used = _find_best_threshold(y_val, event_scores_val)
                logger.info("Threshold ajustado em validação: %.3f", threshold_used)
            else:
                threshold_used = 0.5
                logger.info("Threshold padrão: %.3f (sem validação disponível)", threshold_used)

            # Predição no conjunto de TESTE
            if len(features_test) > 0:
                scores_test = detector.predict(features_test)
                event_scores_test = _align_scores_to_events(test_events, features_test, scores_test)
                y_pred_model = (event_scores_test >= threshold_used).astype(int)

                # PR-AUC usa scores contínuos (não binarizados)
                report_model = compute_metrics(
                    y_test, y_pred_model,
                    f"isolation_forest_{settings.model_version}",
                    y_score=event_scores_test,
                )
                logger.info(
                    "IsolationForest — F1 macro: %s | recall: %s | PR-AUC: %s | FPR: %s",
                    report_model.macro_f1,
                    next((pc.recall for pc in report_model.per_class if pc.label == "anomaly"), None),
                    report_model.pr_auc,
                    report_model.false_positive_rate,
                )

                comparison_vs_majority = compare_detectors(report_majority, report_model)
                comparison_vs_rules = compare_detectors(report_rules, report_model)

                logger.info(
                    "Resultado vs majority: %s | vs rules: %s",
                    "SUPERA" if comparison_vs_majority.challenger_beats_baseline else "NÃO supera",
                    "SUPERA" if comparison_vs_rules.challenger_beats_baseline else "NÃO supera",
                )
            else:
                logger.warning("Nenhuma feature de teste disponível — modelo não avaliado.")

        except FileNotFoundError:
            logger.warning(
                "Artefatos do modelo não encontrados em '%s'. "
                "Execute train_model.py primeiro ou use --no-model.",
                args.model_dir,
            )
        except ImportError as exc:
            logger.warning(
                "sklearn não disponível neste ambiente (%s). "
                "Avaliando apenas baselines. "
                "Ver docs/model-card.md seção 'Limitações de Ambiente'.",
                exc,
            )

    # ── Impressão do relatório ─────────────────────────────────────────────
    _print_summary(
        test_events, y_test, report_majority, report_rules,
        report_model, comparison_vs_majority, comparison_vs_rules,
        threshold_used,
    )

    # ── Salva relatório JSON ───────────────────────────────────────────────
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"evaluation_{settings.model_version}.json"

    full_report: dict = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "model_version": settings.model_version,
        "split": {
            "n_train": len(train_events),
            "n_val": len(val_events),
            "n_test": len(test_events),
            "n_anomalies_test": n_pos_test,
            "n_normal_test": n_neg_test,
            "threshold_used": threshold_used,
        },
        "detectors": {
            "majority_class": report_majority.model_dump(mode="json"),
            "rule_based": report_rules.model_dump(mode="json"),
        },
        "disclaimer": (
            "Métricas calculadas sobre dados SINTÉTICOS com rótulos simulados. "
            "Scores NÃO são probabilidades calibradas. "
            "Não generalizam para dados reais sem validação adicional."
        ),
    }

    if report_model is not None:
        full_report["detectors"]["isolation_forest"] = report_model.model_dump(mode="json")
    if comparison_vs_majority is not None:
        full_report["comparison_vs_majority"] = comparison_vs_majority.model_dump(mode="json")
    if comparison_vs_rules is not None:
        full_report["comparison_vs_rules"] = comparison_vs_rules.model_dump(mode="json")

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Relatório salvo: %s", report_path)


# ── Helpers ───────────────────────────────────────────────────────────────


def _align_scores_to_events(
    events: list,
    features_df,
    scores,
) -> "np.ndarray":
    """Alinha scores por IP ao vetor de eventos.

    Para cada evento, usa o score máximo de qualquer janela do seu source_ip.
    IPs sem features recebem score 0.0.
    """
    import numpy as np

    ip_to_score: dict[str, float] = {}
    for i, row in features_df.iterrows():
        ip = str(row["source_ip"])
        score_val = float(scores[i])
        ip_to_score[ip] = max(ip_to_score.get(ip, 0.0), score_val)

    return np.array([
        ip_to_score.get(str(e.source_ip), 0.0)
        for e in events
    ], dtype=np.float64)


def _find_best_threshold(
    y_val: "np.ndarray",
    scores_val: "np.ndarray",
    n_thresholds: int = 20,
) -> float:
    """Encontra threshold que maximiza F1 da classe anomaly em VALIDAÇÃO.

    Avalia n_thresholds candidatos entre min e max dos scores.
    NUNCA deve ser chamado com dados de teste — apenas validação.
    """
    import numpy as np

    if (y_val == 1).sum() == 0:
        return 0.5

    candidates = np.linspace(scores_val.min(), scores_val.max(), n_thresholds)
    best_threshold = 0.5
    best_f1 = -1.0

    for t in candidates:
        y_pred_t = (scores_val >= t).astype(int)
        tp = int(((y_val == 1) & (y_pred_t == 1)).sum())
        fp = int(((y_val == 0) & (y_pred_t == 1)).sum())
        fn = int(((y_val == 1) & (y_pred_t == 0)).sum())
        denom = 2 * tp + fp + fn
        if denom > 0:
            f1 = 2 * tp / denom
            if f1 > best_f1:
                best_f1 = f1
                best_threshold = float(t)

    return best_threshold


def _print_summary(
    test_events,
    y_test,
    report_majority,
    report_rules,
    report_model,
    comparison_vs_majority,
    comparison_vs_rules,
    threshold_used,
) -> None:
    """Imprime resumo formatado no stdout."""
    sep = "=" * 65
    print(f"\n{sep}")
    print("SENTINEL — RELATÓRIO DE AVALIAÇÃO")
    print(sep)
    print(f"  Eventos de teste   : {len(test_events)}")
    print(f"  Anomalias reais    : {int(y_test.sum())}")
    print(f"  Normais reais      : {int((y_test == 0).sum())}")
    if threshold_used is not None:
        print(f"  Threshold (modelo) : {threshold_used:.3f} (ajustado em validação)")
    print()

    def _fmt(v) -> str:
        return f"{v:.4f}" if v is not None else "N/A"

    def _fmt_cm(cm) -> str:
        return f"TP={cm.tp} FP={cm.fp} FN={cm.fn} TN={cm.tn}"

    for report in [report_majority, report_rules, report_model]:
        if report is None:
            continue
        anomaly_pc = next((pc for pc in report.per_class if pc.label == "anomaly"), None)
        print(f"  ── {report.detector_name}")
        print(f"     Precision(anomaly): {_fmt(anomaly_pc.precision if anomaly_pc else None)}")
        print(f"     Recall(anomaly)   : {_fmt(anomaly_pc.recall if anomaly_pc else None)}")
        print(f"     F1(anomaly)       : {_fmt(anomaly_pc.f1 if anomaly_pc else None)}")
        print(f"     macro_F1          : {_fmt(report.macro_f1)}")
        print(f"     FPR               : {_fmt(report.false_positive_rate)}")
        if report.pr_auc is not None:
            print(f"     PR-AUC            : {_fmt(report.pr_auc)}")
        print(f"     Confusion matrix  : {_fmt_cm(report.confusion_matrix)}")
        print()

    if comparison_vs_majority:
        verdict = "SUPERA" if comparison_vs_majority.challenger_beats_baseline else "NÃO supera"
        print(f"  Modelo vs majority_class baseline : {verdict} (ΔF1={_fmt(comparison_vs_majority.delta_macro_f1)})")
    if comparison_vs_rules:
        verdict = "SUPERA" if comparison_vs_rules.challenger_beats_baseline else "NÃO supera"
        print(f"  Modelo vs rule_based baseline     : {verdict} (ΔF1={_fmt(comparison_vs_rules.delta_macro_f1)})")

    print()
    print("  AVISO: métricas sobre dados SINTÉTICOS.")
    print("  Scores NÃO são probabilidades calibradas.")
    print(sep + "\n")


if __name__ == "__main__":
    main()
