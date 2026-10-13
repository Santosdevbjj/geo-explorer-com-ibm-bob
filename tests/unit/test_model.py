"""Testes unitários — src/sentinel/detection/model.py

sklearn tem uma DLL bloqueada em Python 3.14 / Windows AppControl.
Os testes que dependem de sklearn.ensemble.IsolationForest são marcados
com pytest.mark.skipif para serem pulados quando sklearn não está disponível.
O módulo model.py em si DEVE ser importável sem sklearn (lazy import).
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import numpy as np
import pandas as pd
import pytest

# Verifica se sklearn está disponível antes de importar o módulo
_sklearn_available = False
try:
    from sklearn.ensemble import IsolationForest  # noqa: F401

    _sklearn_available = True
except (ImportError, OSError):
    pass

requires_sklearn = pytest.mark.skipif(
    not _sklearn_available,
    reason="sklearn não disponível (DLL bloqueada em Python 3.14 / Windows AppControl)",
)

# model.py deve ser importável mesmo sem sklearn (lazy import)
from sentinel.detection.model import FEATURE_COLUMNS, AnomalyDetector  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_features(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Gera um DataFrame de features sintéticas para testes."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "source_ip": [f"10.0.0.{i % 10}" for i in range(n)],
            "window_start": [
                datetime(2025, 1, 15, 12, 0, tzinfo=UTC) + timedelta(minutes=i)
                for i in range(n)
            ],
            "auth_failure_rate": rng.uniform(0.0, 0.3, n),
            "request_count": rng.integers(0, 50, n).astype(float),
            "unique_paths": rng.integers(0, 10, n).astype(float),
            "failure_ratio": rng.uniform(0.0, 0.3, n),
            "payload_size_mean": rng.uniform(100.0, 2000.0, n),
        }
    )


def _make_anomalous_features(n: int = 5) -> pd.DataFrame:
    """Gera features que simulam comportamento anômalo (valores extremos)."""
    return pd.DataFrame(
        {
            "source_ip": ["evil.ip"] * n,
            "window_start": [
                datetime(2025, 1, 15, 13, 0, tzinfo=UTC) + timedelta(minutes=i)
                for i in range(n)
            ],
            "auth_failure_rate": [0.95, 0.99, 1.0, 0.98, 0.97],
            "request_count": [500.0, 800.0, 1000.0, 750.0, 900.0],
            "unique_paths": [0.0, 1.0, 0.0, 0.0, 1.0],
            "failure_ratio": [0.90, 0.95, 1.0, 0.92, 0.88],
            "payload_size_mean": [8000.0, 9000.0, 10000.0, 8500.0, 9500.0],
        }
    )


# ── Construção e atributos ─────────────────────────────────────────────────


class TestAnomalyDetectorConstruction:
    def test_not_fitted_by_default(self) -> None:
        detector = AnomalyDetector()
        assert detector.is_fitted is False

    def test_predict_on_untrained_returns_zeros(self) -> None:
        """Fallback: detector não treinado retorna zeros sem exceção."""
        detector = AnomalyDetector()
        X = _make_features(n=5)
        scores = detector.predict(X)
        assert len(scores) == 5
        assert (scores == 0.0).all()

    def test_predict_empty_df_on_untrained(self) -> None:
        detector = AnomalyDetector()
        X = pd.DataFrame(columns=FEATURE_COLUMNS)
        scores = detector.predict(X)
        assert len(scores) == 0


# ── Treino ─────────────────────────────────────────────────────────────────


class TestFit:
    def test_fit_marks_as_fitted(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=50)
        detector.fit(X)
        assert detector.is_fitted is True

    def test_fit_returns_self(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=50)
        result = detector.fit(X)
        assert result is detector

    def test_fit_empty_df_does_not_raise(self) -> None:
        """Treinar com DataFrame vazio não deve levantar exceção."""
        detector = AnomalyDetector()
        X = pd.DataFrame(columns=FEATURE_COLUMNS)
        detector.fit(X)  # deve passar sem exceção
        assert detector.is_fitted is False  # não deve marcar como treinado

    def test_fit_with_missing_columns_fills_zeros(self) -> None:
        """Colunas ausentes são preenchidas com 0 automaticamente."""
        detector = AnomalyDetector()
        X = pd.DataFrame({"auth_failure_rate": [0.1, 0.2, 0.3] * 20})
        detector.fit(X)  # não deve levantar exceção


# ── Predição ───────────────────────────────────────────────────────────────


class TestPredict:
    def test_scores_range_0_to_1(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=50)
        detector.fit(X)
        scores = detector.predict(X)
        assert (scores >= 0.0).all()
        assert (scores <= 1.0).all()

    def test_output_length_matches_input(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=30)
        detector.fit(X)
        scores = detector.predict(X)
        assert len(scores) == len(X)

    def test_output_dtype_float64(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=30)
        detector.fit(X)
        scores = detector.predict(X)
        assert scores.dtype == np.float64

    def test_anomalous_features_score_higher(self) -> None:
        """Features anômalas devem receber score mais alto que normais."""
        detector = AnomalyDetector(contamination=0.1, n_estimators=50, random_state=42)
        X_train = _make_features(n=100)
        detector.fit(X_train)

        X_normal = _make_features(n=10, seed=99)
        X_anomalous = _make_anomalous_features(n=5)

        scores_normal = detector.predict(X_normal)
        scores_anomalous = detector.predict(X_anomalous)

        # A média dos scores anômalos deve ser maior
        assert scores_anomalous.mean() > scores_normal.mean()

    def test_predict_empty_returns_empty(self) -> None:
        detector = AnomalyDetector()
        X_train = _make_features(n=50)
        detector.fit(X_train)
        X_empty = pd.DataFrame(columns=FEATURE_COLUMNS)
        scores = detector.predict(X_empty)
        assert len(scores) == 0


# ── Persistência ──────────────────────────────────────────────────────────


class TestSaveLoad:
    def test_save_creates_files(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=50)
        detector.fit(X)
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = detector.save(tmpdir)
            assert paths["model"].exists()
            assert paths["scaler"].exists()

    def test_save_before_fit_raises(self) -> None:
        detector = AnomalyDetector()
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pytest.raises(RuntimeError, match="não está treinado"),
        ):
            detector.save(tmpdir)

    def test_load_restores_fitted_state(self) -> None:
        detector = AnomalyDetector()
        X = _make_features(n=50)
        detector.fit(X)
        with tempfile.TemporaryDirectory() as tmpdir:
            detector.save(tmpdir)
            loaded = AnomalyDetector.load(tmpdir)
            assert loaded.is_fitted is True

    def test_load_predictions_consistent(self) -> None:
        """Predições do modelo carregado devem ser iguais ao original."""
        detector = AnomalyDetector(n_estimators=50, random_state=0)
        X = _make_features(n=50)
        detector.fit(X)
        scores_original = detector.predict(X)
        with tempfile.TemporaryDirectory() as tmpdir:
            detector.save(tmpdir)
            loaded = AnomalyDetector.load(tmpdir)
        scores_loaded = loaded.predict(X)
        np.testing.assert_array_almost_equal(scores_original, scores_loaded)

    def test_load_missing_files_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(FileNotFoundError):
            AnomalyDetector.load(tmpdir)

    def test_roundtrip_scores_in_range(self) -> None:
        detector = AnomalyDetector(n_estimators=20, random_state=1)
        X = _make_features(n=50)
        detector.fit(X)
        with tempfile.TemporaryDirectory() as tmpdir:
            detector.save(tmpdir)
            loaded = AnomalyDetector.load(tmpdir)
        X_new = _make_features(n=10, seed=77)
        scores = loaded.predict(X_new)
        assert (scores >= 0.0).all()
        assert (scores <= 1.0).all()
