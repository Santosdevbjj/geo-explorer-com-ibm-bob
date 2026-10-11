"""Testes unitários — src/sentinel/monitoring/drift.py"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

from sentinel.monitoring.drift import (
    DriftReport,
    compute_psi,
    check_drift,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_features_df(
    n: int = 100,
    seed: int = 42,
    anomalous: bool = False,
) -> pd.DataFrame:
    """Gera DataFrame de features para testes de drift."""
    rng = np.random.default_rng(seed)
    if anomalous:
        # Distribuição muito diferente da normal → drift esperado
        return pd.DataFrame({
            "auth_failure_rate": rng.uniform(0.7, 1.0, n),
            "request_count": rng.integers(200, 500, n).astype(float),
            "failure_ratio": rng.uniform(0.6, 1.0, n),
            "payload_size_mean": rng.uniform(5000.0, 10000.0, n),
        })
    return pd.DataFrame({
        "auth_failure_rate": rng.uniform(0.0, 0.2, n),
        "request_count": rng.integers(0, 30, n).astype(float),
        "failure_ratio": rng.uniform(0.0, 0.2, n),
        "payload_size_mean": rng.uniform(100.0, 1000.0, n),
    })


def _save_reference(df: pd.DataFrame) -> Path:
    """Salva DataFrame como parquet em diretório temporário e retorna o path."""
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "reference_distribution.json"
    df.to_json(path, orient="records", indent=2)
    return path


# ── compute_psi ────────────────────────────────────────────────────────────


class TestComputePSI:
    def test_identical_distributions_near_zero(self) -> None:
        rng = np.random.default_rng(0)
        arr = rng.normal(0, 1, 1000)
        psi = compute_psi(arr, arr.copy())
        assert psi < 0.01

    def test_very_different_distributions_high_psi(self) -> None:
        rng = np.random.default_rng(0)
        ref = rng.normal(0, 1, 500)
        cur = rng.normal(5, 1, 500)  # média muito diferente
        psi = compute_psi(ref, cur)
        assert psi > 0.20

    def test_psi_non_negative(self) -> None:
        rng = np.random.default_rng(1)
        ref = rng.uniform(0, 1, 200)
        cur = rng.uniform(0, 2, 200)
        psi = compute_psi(ref, cur)
        assert psi >= 0.0

    def test_psi_constant_array_returns_zero(self) -> None:
        ref = np.ones(100)
        cur = np.ones(100)
        psi = compute_psi(ref, cur)
        assert psi == 0.0


# ── check_drift ────────────────────────────────────────────────────────────


class TestCheckDrift:
    def test_no_reference_file_returns_no_drift(self) -> None:
        """Sem arquivo de referência, retorna report sem drift (não levanta exceção)."""
        current = _make_features_df(n=50)
        report = check_drift(current, reference_path="/nonexistent/path.parquet")
        assert isinstance(report, DriftReport)
        assert report.drift_detected is False
        assert report.n_reference_samples == 0

    def test_same_distribution_no_drift(self) -> None:
        rng = np.random.default_rng(42)
        ref = _make_features_df(n=200, seed=42)
        cur = _make_features_df(n=100, seed=43)  # mesma distribuição, seed diferente
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path, threshold=0.20)
        assert report.drift_detected is False

    def test_different_distribution_drift_detected(self) -> None:
        ref = _make_features_df(n=200, anomalous=False, seed=0)
        cur = _make_features_df(n=100, anomalous=True, seed=1)
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path, threshold=0.10)
        assert report.drift_detected is True

    def test_report_contains_features(self) -> None:
        ref = _make_features_df(n=100)
        cur = _make_features_df(n=50)
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path)
        assert len(report.features) > 0

    def test_feature_psi_non_negative(self) -> None:
        ref = _make_features_df(n=100)
        cur = _make_features_df(n=50)
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path)
        for f in report.features:
            assert f.psi >= 0.0

    def test_n_samples_correct(self) -> None:
        ref = _make_features_df(n=150)
        cur = _make_features_df(n=75)
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path)
        assert report.n_current_samples == 75
        assert report.n_reference_samples == 150

    def test_threshold_respected(self) -> None:
        """Com threshold muito alto, nenhum drift deve ser detectado."""
        ref = _make_features_df(n=100, anomalous=False)
        cur = _make_features_df(n=50, anomalous=True)
        ref_path = _save_reference(ref)

        report = check_drift(cur, reference_path=ref_path, threshold=999.0)
        assert report.drift_detected is False

    def test_empty_current_returns_report(self) -> None:
        ref = _make_features_df(n=100)
        ref_path = _save_reference(ref)
        cur = pd.DataFrame(columns=ref.columns)

        report = check_drift(cur, reference_path=ref_path)
        assert isinstance(report, DriftReport)
