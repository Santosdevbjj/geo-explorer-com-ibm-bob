"""Testes unitários — src/sentinel/evaluation/metrics.py

Cobre:
- compute_metrics: casos básicos, macro_recall correto, todos os campos
- compute_pr_auc: numpy puro, caso sem positivos, caso perfeito
- compare_detectors: deltas corretos, veredicto positivo e negativo
- PerClassMetrics: F1 por classe, campos None quando denominador = 0
- Ausência de accuracy isolada e ausência de score como probabilidade
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pytest

from sentinel.evaluation.metrics import (
    ComparisonReport,
    MetricsReport,
    compare_detectors,
    compute_metrics,
    compute_pr_auc,
)

# ── Helpers ───────────────────────────────────────────────────────────────


def _perfect_report(name: str = "perfect") -> MetricsReport:
    y = np.array([0, 0, 1, 1])
    return compute_metrics(y, y, name)


def _zero_report(name: str = "zero") -> MetricsReport:
    y_true = np.array([0, 0, 1, 1])
    y_pred = np.array([0, 0, 0, 0])
    return compute_metrics(y_true, y_pred, name)


# ── compute_metrics — casos básicos ───────────────────────────────────────


class TestComputeMetricsBasic:
    def test_perfect_detection(self) -> None:
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        report = compute_metrics(y_true, y_pred, "perfect")
        assert report.confusion_matrix.tp == 2
        assert report.confusion_matrix.fp == 0
        assert report.confusion_matrix.fn == 0
        assert report.confusion_matrix.tn == 2
        assert report.macro_f1 == 1.0

    def test_no_detection_fn_correct(self) -> None:
        """Nenhuma detecção → FN=2, TP=0."""
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 0, 0])
        report = compute_metrics(y_true, y_pred, "no_detection")
        assert report.confusion_matrix.fn == 2
        assert report.confusion_matrix.tp == 0

    def test_no_detection_macro_recall_correct(self) -> None:
        """Com y_pred=0 para todos: recall(anomaly)=0, recall(normal)=1 → macro_recall=0.5."""
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 0, 0])
        report = compute_metrics(y_true, y_pred, "no_detection")
        # recall(anomaly) = TP/(TP+FN) = 0/2 = 0.0
        # recall(normal)  = TN/(TN+FP) = 2/2 = 1.0
        # macro_recall = (0.0 + 1.0) / 2 = 0.5
        assert report.macro_recall == pytest.approx(0.5, abs=1e-9)

    def test_all_false_positives(self) -> None:
        y_true = np.array([0, 0, 0, 0])
        y_pred = np.array([1, 1, 1, 1])
        report = compute_metrics(y_true, y_pred)
        assert report.confusion_matrix.fp == 4
        assert report.confusion_matrix.tp == 0
        # precision(anomaly) = TP/(TP+FP) = 0/4 = 0
        assert report.per_class[1].precision == pytest.approx(0.0, abs=1e-9)

    def test_mismatched_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="comprimentos diferentes"):
            compute_metrics(np.array([0, 1]), np.array([0, 1, 0]))

    def test_returns_metrics_report(self) -> None:
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 1, 0])
        report = compute_metrics(y_true, y_pred)
        assert isinstance(report, MetricsReport)

    def test_disclaimer_not_empty(self) -> None:
        """disclaimer deve ser não-vazio e não deve chamar score de probabilidade sem ressalva."""
        report = compute_metrics(np.array([0, 1]), np.array([0, 1]))
        assert len(report.disclaimer) > 0
        # Garante que a ressalva sobre probabilidade está presente
        assert (
            "probabilidade" in report.disclaimer.lower()
            or "calibr" in report.disclaimer.lower()
        )

    def test_no_accuracy_field(self) -> None:
        """MetricsReport não deve ter campo accuracy — nunca reportado isoladamente."""
        report = compute_metrics(np.array([0, 1]), np.array([0, 1]))
        assert not hasattr(report, "accuracy")


# ── Macro médias corretas ──────────────────────────────────────────────────


class TestMacroMetrics:
    def test_macro_f1_perfect(self) -> None:
        y = np.array([0, 0, 1, 1])
        report = compute_metrics(y, y)
        assert report.macro_f1 == pytest.approx(1.0, abs=1e-9)

    def test_macro_f1_equal_weight(self) -> None:
        """macro_f1 é média simples de F1(normal) e F1(anomaly)."""
        y_true = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        y_pred = np.array([0, 0, 1, 1, 0, 0, 1, 1])  # 50% precision e recall em ambas
        report = compute_metrics(y_true, y_pred)
        # F1(anomaly) = 2*(2/4*2/4)/(2/4+2/4) = 0.5  (TP=2, FP=2, FN=2)
        # F1(normal)  = 2*(2/4*2/4)/(2/4+2/4) = 0.5  (TN=2, FN=2, FP=2)
        # macro_f1 = 0.5
        assert report.macro_f1 == pytest.approx(0.5, abs=1e-3)

    def test_macro_recall_symmetric_case(self) -> None:
        """Caso simétrico: macro_recall = 0.5 quando uma classe tem recall 1 e outra 0."""
        y_true = np.array([0, 1])
        y_pred = np.array([0, 0])  # acerta o normal, erra o anomaly
        report = compute_metrics(y_true, y_pred)
        assert report.macro_recall == pytest.approx(0.5, abs=1e-9)

    def test_macro_precision_none_when_all_zero_pred(self) -> None:
        """Se apenas classe normal é predita, precision(anomaly) = None."""
        y_true = np.array([1, 1, 1])
        y_pred = np.array([0, 0, 0])
        report = compute_metrics(y_true, y_pred)
        anomaly_pc = next(pc for pc in report.per_class if pc.label == "anomaly")
        assert anomaly_pc.precision is None


# ── Per-class metrics ─────────────────────────────────────────────────────


class TestPerClassMetrics:
    def test_per_class_has_two_entries(self) -> None:
        report = compute_metrics(np.array([0, 1, 0, 1]), np.array([0, 1, 1, 0]))
        assert len(report.per_class) == 2

    def test_per_class_labels(self) -> None:
        report = compute_metrics(np.array([0, 1, 0, 1]), np.array([0, 1, 1, 0]))
        labels = {pc.label for pc in report.per_class}
        assert "normal" in labels
        assert "anomaly" in labels

    def test_anomaly_f1_perfect(self) -> None:
        y = np.array([0, 0, 1, 1])
        report = compute_metrics(y, y)
        anomaly_pc = next(pc for pc in report.per_class if pc.label == "anomaly")
        assert anomaly_pc.f1 == pytest.approx(1.0)

    def test_anomaly_recall_zero_on_miss(self) -> None:
        y_true = np.array([1, 1])
        y_pred = np.array([0, 0])
        report = compute_metrics(y_true, y_pred)
        anomaly_pc = next(pc for pc in report.per_class if pc.label == "anomaly")
        assert anomaly_pc.recall == pytest.approx(0.0, abs=1e-9)

    def test_support_correct(self) -> None:
        y_true = np.array([0, 0, 0, 1, 1])
        y_pred = np.array([0, 0, 0, 1, 1])
        report = compute_metrics(y_true, y_pred)
        normal_pc = next(pc for pc in report.per_class if pc.label == "normal")
        anomaly_pc = next(pc for pc in report.per_class if pc.label == "anomaly")
        assert normal_pc.support == 3
        assert anomaly_pc.support == 2

    def test_f1_both_classes_correct(self) -> None:
        """F1 por classe deve ser consistente com precision e recall."""
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 1, 1, 0])  # TP=1, FP=1, FN=1, TN=1
        report = compute_metrics(y_true, y_pred)
        anomaly_pc = next(pc for pc in report.per_class if pc.label == "anomaly")
        if anomaly_pc.precision is not None and anomaly_pc.recall is not None:
            expected_f1 = (
                2
                * anomaly_pc.precision
                * anomaly_pc.recall
                / (anomaly_pc.precision + anomaly_pc.recall)
            )
            assert anomaly_pc.f1 == pytest.approx(expected_f1, abs=1e-9)


# ── FPR ───────────────────────────────────────────────────────────────────


class TestFalsePositiveRate:
    def test_fpr_zero_perfect(self) -> None:
        y = np.array([0, 0, 1, 1])
        report = compute_metrics(y, y)
        assert report.false_positive_rate == pytest.approx(0.0, abs=1e-9)

    def test_fpr_one_all_positive_pred(self) -> None:
        y_true = np.array([0, 0, 0, 1])
        y_pred = np.array([1, 1, 1, 1])
        report = compute_metrics(y_true, y_pred)
        assert report.false_positive_rate == pytest.approx(1.0, abs=1e-9)

    def test_fpr_none_when_no_negatives(self) -> None:
        y_true = np.array([1, 1, 1])
        y_pred = np.array([1, 0, 1])
        report = compute_metrics(y_true, y_pred)
        assert report.false_positive_rate is None


# ── compute_pr_auc ────────────────────────────────────────────────────────


class TestComputePrAuc:
    def test_perfect_pr_auc_is_one(self) -> None:
        """Score perfeito → PR-AUC = 1.0."""
        y_true = np.array([0, 0, 1, 1])
        y_score = np.array([0.1, 0.2, 0.8, 0.9])
        auc = compute_pr_auc(y_true, y_score)
        assert auc is not None
        assert auc == pytest.approx(1.0, abs=1e-6)

    def test_pr_auc_none_when_no_positives(self) -> None:
        y_true = np.array([0, 0, 0, 0])
        y_score = np.array([0.1, 0.9, 0.5, 0.3])
        assert compute_pr_auc(y_true, y_score) is None

    def test_pr_auc_in_range(self) -> None:
        y_true = np.array([0, 1, 0, 1, 0, 1])
        y_score = np.array([0.1, 0.9, 0.4, 0.6, 0.3, 0.7])
        auc = compute_pr_auc(y_true, y_score)
        assert auc is not None
        assert 0.0 <= auc <= 1.0

    def test_pr_auc_with_compute_metrics(self) -> None:
        """compute_metrics deve propagar PR-AUC quando y_score fornecido."""
        y_true = np.array([0, 0, 1, 1])
        y_pred = np.array([0, 0, 1, 1])
        y_score = np.array([0.1, 0.2, 0.8, 0.9])
        report = compute_metrics(y_true, y_pred, y_score=y_score)
        assert report.pr_auc is not None
        assert report.pr_auc == pytest.approx(1.0, abs=1e-6)

    def test_pr_auc_none_when_no_score_given(self) -> None:
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 1, 0, 1])
        report = compute_metrics(y_true, y_pred)
        assert report.pr_auc is None

    def test_pr_auc_not_labeled_as_probability(self) -> None:
        """Campo pr_auc do MetricsReport deve ter disclaimer sobre não ser probabilidade."""
        field_info = MetricsReport.model_fields.get("pr_auc")
        assert field_info is not None
        description = field_info.description or ""
        assert "probabilidade" in description.lower() or "calibr" in description.lower()

    def test_random_scores_auc_near_baseline(self) -> None:
        """Scores aleatórios devem produzir PR-AUC próximo à prevalência."""
        rng = np.random.default_rng(42)
        n = 1000
        prevalence = 0.1
        y_true = (rng.random(n) < prevalence).astype(int)
        y_score = rng.random(n)
        auc = compute_pr_auc(y_true, y_score)
        assert auc is not None
        # PR-AUC aleatório ≈ prevalência; aceitamos ±0.1
        assert abs(auc - prevalence) < 0.1


# ── compare_detectors ─────────────────────────────────────────────────────


class TestCompareDetectors:
    def test_perfect_beats_zero(self) -> None:
        baseline = _zero_report("zero")
        challenger = _perfect_report("perfect")
        result = compare_detectors(baseline, challenger)
        assert result.challenger_beats_baseline is True
        assert result.delta_macro_f1 is not None
        assert result.delta_macro_f1 > 0

    def test_zero_does_not_beat_perfect(self) -> None:
        baseline = _perfect_report("perfect")
        challenger = _zero_report("zero")
        result = compare_detectors(baseline, challenger)
        assert result.challenger_beats_baseline is False
        assert result.delta_macro_f1 is not None
        assert result.delta_macro_f1 < 0

    def test_analysis_documents_non_improvement(self) -> None:
        """Se o challenger não supera, a análise deve documentar explicitamente."""
        baseline = _perfect_report("perfect")
        challenger = _zero_report("zero")
        result = compare_detectors(baseline, challenger)
        assert (
            "NÃO supera" in result.analysis or "não supera" in result.analysis.lower()
        )

    def test_analysis_documents_improvement(self) -> None:
        baseline = _zero_report("zero")
        challenger = _perfect_report("perfect")
        result = compare_detectors(baseline, challenger)
        assert "supera" in result.analysis.lower()

    def test_delta_recall_correct(self) -> None:
        """delta_recall deve ser recall(challenger) - recall(baseline) para anomaly."""
        y_true = np.array([0, 0, 1, 1, 0, 0, 1, 1])
        y_pred_base = np.array([0, 0, 1, 0, 0, 0, 1, 0])  # recall anomaly = 0.5
        y_pred_chall = np.array([0, 0, 1, 1, 0, 0, 1, 1])  # recall anomaly = 1.0
        base = compute_metrics(y_true, y_pred_base, "base")
        chall = compute_metrics(y_true, y_pred_chall, "chall")
        result = compare_detectors(base, chall)
        assert result.delta_recall is not None
        assert result.delta_recall == pytest.approx(0.5, abs=1e-9)

    def test_delta_fpr_correct(self) -> None:
        """delta_fpr negativo indica challenger tem menos FPs (melhor)."""
        y_true = np.array([0, 0, 0, 0, 1, 1])
        y_pred_base = np.array([1, 1, 0, 0, 1, 1])  # FPR = 2/4 = 0.5
        y_pred_chall = np.array([0, 0, 0, 0, 1, 1])  # FPR = 0
        base = compute_metrics(y_true, y_pred_base, "base")
        chall = compute_metrics(y_true, y_pred_chall, "chall")
        result = compare_detectors(base, chall)
        assert result.delta_fpr is not None
        assert result.delta_fpr < 0  # challenger tem menos FPs

    def test_comparison_report_fields(self) -> None:
        result = compare_detectors(_zero_report(), _perfect_report())
        assert isinstance(result, ComparisonReport)
        assert result.baseline_name == "zero"
        assert result.challenger_name == "perfect"
        assert len(result.disclaimer) > 0
        assert len(result.analysis) > 0

    def test_analysis_always_contains_warning(self) -> None:
        """Toda análise deve conter aviso sobre dados sintéticos."""
        result = compare_detectors(_zero_report(), _perfect_report())
        assert (
            "sintéticos" in result.analysis.lower()
            or "não generalizam" in result.analysis.lower()
        )


# ── Contagens e n_samples ─────────────────────────────────────────────────


class TestCounts:
    def test_n_samples_correct(self) -> None:
        y_true = np.array([0, 1, 0, 1, 0])
        y_pred = np.array([0, 1, 0, 0, 1])
        report = compute_metrics(y_true, y_pred)
        assert report.n_samples == 5

    def test_n_positive_correct(self) -> None:
        y_true = np.array([0, 1, 1, 0, 1])
        y_pred = np.array([0, 0, 0, 0, 0])
        report = compute_metrics(y_true, y_pred)
        assert report.n_positive == 3

    def test_n_negative_correct(self) -> None:
        y_true = np.array([0, 1, 0, 1])
        y_pred = np.array([0, 0, 0, 0])
        report = compute_metrics(y_true, y_pred)
        assert report.n_negative == 2


# ── Edge cases ────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_all_normal_in_true(self) -> None:
        y_true = np.array([0, 0, 0, 0])
        y_pred = np.array([0, 0, 0, 0])
        report = compute_metrics(y_true, y_pred)
        assert report.n_positive == 0
        assert report.confusion_matrix.fn == 0
        assert report.confusion_matrix.tp == 0

    def test_all_anomaly_in_true(self) -> None:
        y_true = np.array([1, 1, 1, 1])
        y_pred = np.array([1, 1, 0, 0])
        report = compute_metrics(y_true, y_pred)
        assert report.confusion_matrix.tp == 2
        assert report.confusion_matrix.fn == 2
        assert report.confusion_matrix.tn == 0

    def test_single_sample_anomaly_detected(self) -> None:
        report = compute_metrics(np.array([1]), np.array([1]))
        assert report.confusion_matrix.tp == 1
        assert report.macro_f1 == pytest.approx(1.0, abs=1e-9)

    def test_single_sample_missed(self) -> None:
        report = compute_metrics(np.array([1]), np.array([0]))
        assert report.confusion_matrix.fn == 1
        # recall(anomaly) = 0, recall(normal) = None (sem TN) → macro_recall = None ou 0
        # apenas garantimos que não levanta exceção e que o FN está correto
        assert report.confusion_matrix.fn == 1
