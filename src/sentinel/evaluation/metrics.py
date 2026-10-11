"""Métricas de avaliação de modelos de detecção do Sentinel.

Calcula precision, recall, F1, PR-AUC, matriz de confusão, falsos positivos e
comparação com baseline determinística — tudo em numpy puro, sem depender de
sklearn.metrics (que tem DLL bloqueada em Python 3.14 / Windows AppControl).

PRINCÍPIOS:
- Nunca inventar métricas: se o denominador for zero, retorna None.
- Não chamar score de "probabilidade" sem calibração documentada.
- Accuracy não é usada isoladamente como indicador de desempenho.
- PR-AUC é calculado com interpolação trapezoidal em numpy (não usa sklearn).
- macro_f1 é calculado como média de F1 por classe (não como F1 global).
- Comparações com baseline são documentadas mesmo se o modelo não superar.

IMPORTANTE: métricas calculadas sobre dados sintéticos não se transferem
diretamente para dados reais. Ver docs/model-card.md.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from pydantic import BaseModel, Field


# ── Schemas de saída ───────────────────────────────────────────────────────


class PerClassMetrics(BaseModel):
    """Métricas para uma classe específica."""

    label: str
    precision: float | None = Field(description="TP / (TP + FP). None se denominador = 0.")
    recall: float | None = Field(description="TP / (TP + FN). None se denominador = 0.")
    f1: float | None = Field(description="Média harmônica de precision e recall. None se impossível.")
    support: int = Field(description="Total de amostras desta classe em y_true.")


class ConfusionMatrix(BaseModel):
    """Matriz de confusão binária."""

    tp: int = Field(description="True Positives: anomalia real detectada.")
    fp: int = Field(description="False Positives: normal classificado como anomalia.")
    fn: int = Field(description="False Negatives: anomalia real não detectada.")
    tn: int = Field(description="True Negatives: normal classificado como normal.")


class MetricsReport(BaseModel):
    """Resultado completo da avaliação binária de um detector.

    Inclui aviso explícito sobre limitações da avaliação.
    Accuracy não é reportada isoladamente — use macro_f1 e false_positive_rate.
    """

    detector_name: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    n_samples: int
    n_positive: int = Field(description="Total de anomalias reais em y_true.")
    n_negative: int = Field(description="Total de normais reais em y_true.")
    confusion_matrix: ConfusionMatrix
    # macro_precision e macro_recall são médias não-ponderadas das classes normal e anomaly
    macro_precision: float | None = Field(
        description="Média de precision(normal) + precision(anomaly) / 2."
    )
    macro_recall: float | None = Field(
        description="Média de recall(normal) + recall(anomaly) / 2."
    )
    macro_f1: float | None = Field(
        description="Média de F1(normal) + F1(anomaly) / 2. Não é F1 global."
    )
    false_positive_rate: float | None = Field(
        description="FP / (FP + TN). Taxa de falsos positivos sobre os normais."
    )
    pr_auc: float | None = Field(
        default=None,
        description=(
            "Área sob a curva Precision-Recall (interpolação trapezoidal). "
            "Calculada quando y_score está disponível. "
            "NÃO é uma probabilidade calibrada."
        ),
    )
    per_class: list[PerClassMetrics] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "Métricas calculadas sobre dados sintéticos com rótulos simulados. "
            "Não representam desempenho em dados reais. "
            "Scores não são probabilidades calibradas."
        ),
    )


class ComparisonReport(BaseModel):
    """Comparação entre dois ou mais detectores.

    Documenta se o modelo supera a baseline — incluindo casos em que não supera.
    """

    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_name: str
    challenger_name: str
    baseline: MetricsReport
    challenger: MetricsReport
    # Deltas: positivo = challenger melhor; negativo = baseline melhor
    delta_macro_f1: float | None = Field(
        description="challenger.macro_f1 - baseline.macro_f1. None se algum for None."
    )
    delta_recall: float | None = Field(
        description="delta do recall da classe anomaly (sensibilidade a ataques)."
    )
    delta_fpr: float | None = Field(
        description="delta de false_positive_rate. Negativo = challenger tem menos FPs."
    )
    challenger_beats_baseline: bool | None = Field(
        description=(
            "True se challenger.macro_f1 > baseline.macro_f1. "
            "None se não calculável. "
            "False é documentado, não ocultado."
        ),
    )
    analysis: str = Field(
        description=(
            "Análise textual do resultado da comparação. "
            "Documenta limitações e contexto, incluindo quando o modelo não supera a baseline."
        ),
    )
    disclaimer: str = Field(
        default=(
            "Comparação sobre dados sintéticos. "
            "Não representa desempenho relativo em dados reais. "
            "Scores não são probabilidades calibradas."
        ),
    )


# ── Funções de cálculo ─────────────────────────────────────────────────────


def _safe_div(num: float, denom: float) -> float | None:
    """Divisão segura: retorna None se denominador ≈ 0."""
    if abs(denom) < 1e-12:
        return None
    return num / denom


def _f1_from_p_r(precision: float | None, recall: float | None) -> float | None:
    """Calcula F1 a partir de precision e recall. Retorna None se impossível."""
    if precision is None or recall is None:
        return None
    denom = precision + recall
    if abs(denom) < 1e-12:
        return 0.0
    return 2.0 * precision * recall / denom


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    detector_name: str = "unknown",
    y_score: np.ndarray | None = None,
) -> MetricsReport:
    """Calcula métricas de avaliação binária.

    Args:
        y_true: Array de inteiros (0 = normal, 1 = anomalia real).
        y_pred: Array de inteiros binarizados (0 = não detectado, 1 = detectado).
        detector_name: Nome do detector sendo avaliado.
        y_score: Scores contínuos (0–1) para cálculo de PR-AUC. Opcional.
                 NÃO interpreta como probabilidade calibrada.

    Returns:
        MetricsReport com métricas reais (sem calibração).

    Raises:
        ValueError: Se y_true e y_pred tiverem comprimentos diferentes.

    Note:
        Accuracy não é reportada isoladamente.
        macro_f1 é média de F1(normal) e F1(anomaly), não F1 global.
    """
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true ({len(y_true)}) e y_pred ({len(y_pred)}) têm comprimentos diferentes."
        )

    y_t = np.asarray(y_true, dtype=int)
    y_p = np.asarray(y_pred, dtype=int)

    tp = int(((y_t == 1) & (y_p == 1)).sum())
    fp = int(((y_t == 0) & (y_p == 1)).sum())
    fn = int(((y_t == 1) & (y_p == 0)).sum())
    tn = int(((y_t == 0) & (y_p == 0)).sum())

    n_positive = int((y_t == 1).sum())
    n_negative = int((y_t == 0).sum())

    # Métricas da classe anomaly (positiva)
    prec_anomaly = _safe_div(tp, tp + fp)
    rec_anomaly = _safe_div(tp, tp + fn)
    f1_anomaly = _f1_from_p_r(prec_anomaly, rec_anomaly)

    # Métricas da classe normal (negativa — invertendo TP/FP/FN/TN)
    prec_normal = _safe_div(tn, tn + fn)
    rec_normal = _safe_div(tn, tn + fp)
    f1_normal = _f1_from_p_r(prec_normal, rec_normal)

    # Macro médias (média simples das duas classes)
    macro_precision: float | None
    if prec_anomaly is not None and prec_normal is not None:
        macro_precision = (prec_anomaly + prec_normal) / 2.0
    elif prec_anomaly is not None:
        macro_precision = prec_anomaly
    elif prec_normal is not None:
        macro_precision = prec_normal
    else:
        macro_precision = None

    macro_recall: float | None
    if rec_anomaly is not None and rec_normal is not None:
        macro_recall = (rec_anomaly + rec_normal) / 2.0
    elif rec_anomaly is not None:
        macro_recall = rec_anomaly
    elif rec_normal is not None:
        macro_recall = rec_normal
    else:
        macro_recall = None

    macro_f1: float | None
    if f1_anomaly is not None and f1_normal is not None:
        macro_f1 = (f1_anomaly + f1_normal) / 2.0
    elif f1_anomaly is not None:
        macro_f1 = f1_anomaly
    elif f1_normal is not None:
        macro_f1 = f1_normal
    else:
        macro_f1 = None

    fpr = _safe_div(fp, fp + tn)

    # PR-AUC via interpolação trapezoidal (numpy puro, sem sklearn.metrics)
    pr_auc: float | None = None
    if y_score is not None and n_positive > 0:
        pr_auc = compute_pr_auc(y_t, np.asarray(y_score, dtype=float))

    per_class = [
        PerClassMetrics(
            label="normal",
            precision=prec_normal,
            recall=rec_normal,
            f1=f1_normal,
            support=n_negative,
        ),
        PerClassMetrics(
            label="anomaly",
            precision=prec_anomaly,
            recall=rec_anomaly,
            f1=f1_anomaly,
            support=n_positive,
        ),
    ]

    return MetricsReport(
        detector_name=detector_name,
        n_samples=len(y_t),
        n_positive=n_positive,
        n_negative=n_negative,
        confusion_matrix=ConfusionMatrix(tp=tp, fp=fp, fn=fn, tn=tn),
        macro_precision=macro_precision,
        macro_recall=macro_recall,
        macro_f1=macro_f1,
        false_positive_rate=fpr,
        pr_auc=pr_auc,
        per_class=per_class,
    )


def compute_pr_auc(y_true: np.ndarray, y_score: np.ndarray) -> float | None:
    """Calcula a área sob a curva Precision-Recall (PR-AUC) com numpy.

    Usa interpolação trapezoidal sobre a curva PR ordenada por threshold decrescente.
    Implementação em numpy puro — não depende de sklearn.metrics.

    Args:
        y_true: Array binário (0/1).
        y_score: Scores contínuos (maiores = mais anômalo). NÃO é probabilidade.

    Returns:
        PR-AUC como float em [0, 1], ou None se n_positive = 0.

    Note:
        O ponto inicial da curva PR é (recall=0, precision=1) por convenção,
        mantido por adição do ponto sentinela.
        O valor retornado NÃO é uma probabilidade calibrada.
    """
    y_t = np.asarray(y_true, dtype=int)
    y_s = np.asarray(y_score, dtype=float)

    n_positive = int((y_t == 1).sum())
    if n_positive == 0:
        return None

    # Ordena por score decrescente
    order = np.argsort(-y_s)
    y_t_sorted = y_t[order]

    tp_cumsum = np.cumsum(y_t_sorted)
    fp_cumsum = np.cumsum(1 - y_t_sorted)

    n = len(y_t_sorted)
    total = np.arange(1, n + 1)

    precision_curve = tp_cumsum / total
    recall_curve = tp_cumsum / n_positive

    # Adiciona ponto sentinela (recall=0, precision=1) no início
    precision_curve = np.concatenate([[1.0], precision_curve])
    recall_curve = np.concatenate([[0.0], recall_curve])

    # Integração trapezoidal
    auc: float = float(np.trapz(precision_curve, recall_curve))
    return auc


def compare_detectors(
    baseline: MetricsReport,
    challenger: MetricsReport,
) -> ComparisonReport:
    """Compara dois relatórios de métricas e documenta o resultado.

    Documenta explicitamente quando o challenger NÃO supera a baseline.

    Args:
        baseline: MetricsReport do detector de referência.
        challenger: MetricsReport do detector a ser avaliado.

    Returns:
        ComparisonReport com deltas e análise textual.
    """
    # Delta de macro_f1
    delta_f1: float | None = None
    if baseline.macro_f1 is not None and challenger.macro_f1 is not None:
        delta_f1 = challenger.macro_f1 - baseline.macro_f1

    # Delta de recall (classe anomaly — sensibilidade a ataques)
    delta_recall: float | None = None
    b_rec = next((pc.recall for pc in baseline.per_class if pc.label == "anomaly"), None)
    c_rec = next((pc.recall for pc in challenger.per_class if pc.label == "anomaly"), None)
    if b_rec is not None and c_rec is not None:
        delta_recall = c_rec - b_rec

    # Delta de FPR (menor é melhor para o challenger)
    delta_fpr: float | None = None
    if baseline.false_positive_rate is not None and challenger.false_positive_rate is not None:
        delta_fpr = challenger.false_positive_rate - baseline.false_positive_rate

    # Veredicto
    beats: bool | None = None
    if delta_f1 is not None:
        beats = delta_f1 > 0.0

    # Análise textual — documenta mesmo resultado negativo
    analysis = _build_analysis(baseline, challenger, delta_f1, delta_recall, delta_fpr, beats)

    return ComparisonReport(
        baseline_name=baseline.detector_name,
        challenger_name=challenger.detector_name,
        baseline=baseline,
        challenger=challenger,
        delta_macro_f1=delta_f1,
        delta_recall=delta_recall,
        delta_fpr=delta_fpr,
        challenger_beats_baseline=beats,
        analysis=analysis,
    )


def _build_analysis(
    baseline: MetricsReport,
    challenger: MetricsReport,
    delta_f1: float | None,
    delta_recall: float | None,
    delta_fpr: float | None,
    beats: bool | None,
) -> str:
    """Constrói análise textual da comparação entre detectores."""
    lines: list[str] = []

    if beats is None:
        lines.append(
            "Comparação não conclusiva: macro_F1 não calculável para um ou ambos os detectores."
        )
    elif beats:
        lines.append(
            f"Challenger '{challenger.detector_name}' supera a baseline '{baseline.detector_name}' "
            f"em macro_F1 (+{delta_f1:.4f})."
        )
    else:
        lines.append(
            f"Challenger '{challenger.detector_name}' NÃO supera a baseline '{baseline.detector_name}' "
            f"em macro_F1 ({delta_f1:+.4f}). "
            "Investigar: possível subajuste, janela inadequada ou contaminação incorreta."
        )

    if delta_recall is not None:
        direction = "melhor" if delta_recall > 0 else "pior"
        lines.append(
            f"Recall (detecção de anomalias): {direction} no challenger "
            f"({delta_recall:+.4f}). "
            "Recall baixo implica mais anomalias não detectadas."
        )

    if delta_fpr is not None:
        direction = "menos" if delta_fpr < 0 else "mais"
        lines.append(
            f"Taxa de falsos positivos: challenger tem {direction} FPs "
            f"({delta_fpr:+.4f}). "
            "FPR alto sobrecarrega analistas com alertas sem incidente real."
        )

    if challenger.pr_auc is not None:
        lines.append(
            f"PR-AUC do challenger: {challenger.pr_auc:.4f} "
            "(interpolação trapezoidal; NÃO é probabilidade calibrada)."
        )

    lines.append(
        "Aviso: métricas sobre dados sintéticos. "
        "Validar com dados reais antes de decisões operacionais."
    )

    return " | ".join(lines)
