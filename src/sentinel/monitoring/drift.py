"""Monitoramento de data drift do Sentinel.

Detecta desvio na distribuição de features usando PSI
(Population Stability Index).

PSI ≤ 0.10  → sem drift significativo
PSI 0.10–0.20 → drift moderado (monitorar)
PSI > 0.20  → drift severo (considerar retreino)

Referência versionada salva em JSON: data/processed/reference_distribution.json
Threshold configurável via: DRIFT_ALERT_THRESHOLD no .env
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from sentinel.config import settings

logger = logging.getLogger(__name__)

# Colunas monitoradas (subset das features do modelo)
MONITORED_FEATURES: list[str] = [
    "auth_failure_rate",
    "request_count",
    "failure_ratio",
    "payload_size_mean",
]


# ── Schema de saída ────────────────────────────────────────────────────────


class FeatureDrift(BaseModel):
    """Resultado de drift para uma feature individual."""

    feature: str
    psi: float = Field(description="Population Stability Index para esta feature.")
    drift_detected: bool = Field(description="True se PSI > threshold.")
    n_bins: int


class DriftReport(BaseModel):
    """Resultado completo da verificação de drift."""

    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    drift_detected: bool = Field(description="True se alguma feature ultrapassou o threshold.")
    threshold: float
    n_current_samples: int
    n_reference_samples: int
    features: list[FeatureDrift] = Field(default_factory=list)
    message: str = ""


# ── PSI ────────────────────────────────────────────────────────────────────


def compute_psi(
    reference: np.ndarray,
    current: np.ndarray,
    n_bins: int = 10,
    epsilon: float = 1e-8,
) -> float:
    """Calcula o PSI entre distribuições de referência e atual.

    Args:
        reference: Array da distribuição de referência (treino).
        current: Array da distribuição atual (produção/teste).
        n_bins: Número de bins para o histograma.
        epsilon: Valor mínimo para evitar divisão por zero.

    Returns:
        Valor PSI (float ≥ 0). PSI > 0.20 indica drift severo.
    """
    # Amostras vazias ou não finitas não sustentam uma comparação válida.
    reference = np.asarray(reference, dtype=float)
    current = np.asarray(current, dtype=float)
    reference = reference[np.isfinite(reference)]
    current = current[np.isfinite(current)]
    if reference.size == 0 or current.size == 0:
        return 0.0

    # Define bins a partir da referência
    min_val = min(reference.min(), current.min())
    max_val = max(reference.max(), current.max())

    if max_val - min_val < 1e-9:
        return 0.0

    bins = np.linspace(min_val, max_val, n_bins + 1)

    ref_counts, _ = np.histogram(reference, bins=bins)
    cur_counts, _ = np.histogram(current, bins=bins)

    # Normaliza para proporções (adicionando epsilon para bins vazios)
    ref_pct = (ref_counts + epsilon) / (ref_counts.sum() + epsilon * n_bins)
    cur_pct = (cur_counts + epsilon) / (cur_counts.sum() + epsilon * n_bins)

    psi_values = (cur_pct - ref_pct) * np.log(cur_pct / ref_pct)
    return float(psi_values.sum())


# ── Verificação de drift ───────────────────────────────────────────────────


def check_drift(
    current_features: pd.DataFrame,
    reference_path: str | Path | None = None,
    threshold: float | None = None,
    n_bins: int = 10,
) -> DriftReport:
    """Verifica drift entre features atuais e distribuição de referência.

    Args:
        current_features: DataFrame com features da janela atual.
        reference_path: Caminho do JSON de referência (aceita parquet legado; usa settings se None).
        threshold: Threshold PSI para alertar (usa settings se None).
        n_bins: Número de bins para o histograma PSI.

    Returns:
        DriftReport com status por feature. Nunca levanta exceção de dados.
    """
    ref_path = Path(reference_path or settings.drift_reference_path)
    thr = threshold if threshold is not None else settings.drift_alert_threshold

    if not 0.0 < thr <= 10.0:
        return DriftReport(
            drift_detected=False,
            threshold=thr,
            n_current_samples=len(current_features),
            n_reference_samples=0,
            message="Threshold inválido; informe valor maior que 0 e até 10.",
        )
    if len(current_features) < 20:
        return DriftReport(
            drift_detected=False,
            threshold=thr,
            n_current_samples=len(current_features),
            n_reference_samples=0,
            message="Amostra atual insuficiente para avaliar drift (mínimo operacional: 20).",
        )

    # ── Verifica referência ────────────────────────────────────────────────
    if not ref_path.exists():
        msg = (
            f"Arquivo de referência não encontrado: {ref_path}. "
            "Execute scripts/train_model.py para gerar a distribuição de referência."
        )
        logger.warning(msg)
        return DriftReport(
            drift_detected=False,
            threshold=thr,
            n_current_samples=len(current_features),
            n_reference_samples=0,
            message=msg,
        )

    # ── Carrega referência ─────────────────────────────────────────────────
    try:
        if ref_path.suffix.lower() == ".json":
            reference_df = pd.read_json(ref_path)
        elif ref_path.suffix.lower() in {".parquet", ".pq"}:
            # Compatibilidade com artefatos antigos; requer pyarrow/fastparquet.
            reference_df = pd.read_parquet(ref_path)
        else:
            raise ValueError("Formato de referência não suportado; use .json ou .parquet.")
    except Exception as exc:  # noqa: BLE001
        msg = f"Erro ao carregar referência: {exc}"
        logger.error(msg)
        return DriftReport(
            drift_detected=False,
            threshold=thr,
            n_current_samples=len(current_features),
            n_reference_samples=0,
            message=msg,
        )

    # ── Calcula PSI por feature ────────────────────────────────────────────
    feature_results: list[FeatureDrift] = []
    any_drift = False

    for feature in MONITORED_FEATURES:
        if feature not in reference_df.columns or feature not in current_features.columns:
            logger.warning("Feature '%s' ausente na referência ou atual — ignorada.", feature)
            continue

        ref_arr = reference_df[feature].dropna().to_numpy(dtype=float)
        cur_arr = current_features[feature].dropna().to_numpy(dtype=float)

        if len(ref_arr) == 0 or len(cur_arr) == 0:
            logger.warning("Feature '%s' vazia — ignorada no drift check.", feature)
            continue

        psi = compute_psi(ref_arr, cur_arr, n_bins=n_bins)
        detected = psi > thr
        if detected:
            any_drift = True
            logger.warning("Drift detectado em '%s': PSI=%.4f (threshold=%.4f)", feature, psi, thr)

        feature_results.append(
            FeatureDrift(
                feature=feature,
                psi=round(psi, 6),
                drift_detected=detected,
                n_bins=n_bins,
            )
        )

    return DriftReport(
        drift_detected=any_drift,
        threshold=thr,
        n_current_samples=len(current_features),
        n_reference_samples=len(reference_df),
        features=feature_results,
        message="OK" if not any_drift else f"Drift detectado em {sum(f.drift_detected for f in feature_results)} feature(s).",
    )
