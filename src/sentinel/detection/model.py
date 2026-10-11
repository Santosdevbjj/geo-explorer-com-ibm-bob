"""Modelo ML de linha de base do Sentinel — IsolationForest.

Responsabilidades:
- Treinar um detector de anomalias não-supervisionado sobre features extraídas
- Serializar e desserializar o artefato de modelo + scaler
- Predizer anomaly_score por linha de features (0 = normal, 1 = anomalia forte)
- Operar em modo fallback (retornar zeros) se o artefato não for encontrado

O score de anomalia NÃO é uma probabilidade calibrada.
Não o apresente como probabilidade sem calibração explícita.

LIMITAÇÃO DE AMBIENTE:
sklearn 1.9.0 + Python 3.14 neste ambiente tem uma DLL bloqueada por política
AppControl do Windows (_radius_neighbors). Isso não afeta o CI (Python 3.12 /
Ubuntu). Documentado em docs/decisions/ADR-002 e docs/model-card.md.
O import do sklearn é feito de forma lazy (dentro dos métodos) para que este
módulo seja importável mesmo quando sklearn está bloqueado — permitindo que
outros módulos que importam apenas FEATURE_COLUMNS ou AnomalyDetector para
type-checking continuem funcionando.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from sentinel.config import settings

if TYPE_CHECKING:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Colunas de features usadas pelo modelo
# Deve estar em sincronia com engineering.FEATURE_COLUMNS (excluindo identificadores)
FEATURE_COLUMNS: list[str] = [
    "auth_failure_rate",
    "auth_failure_count",
    "request_count",
    "unique_paths",
    "req_per_second",
    "scan_path_hits",
    "failure_ratio",
    "error_count",
    "timeout_ratio",
    "payload_size_mean",
    "payload_size_std",
    "inter_event_mean_ms",
    "inter_event_min_ms",
    "scanner_agent_ratio",
]


class AnomalyDetector:
    """Detector de anomalias baseado em IsolationForest com StandardScaler embutido.

    Fluxo:
        1. fit(X)       → treina scaler e IsolationForest
        2. predict(X)   → retorna array de anomaly_score por linha (0.0–1.0)
        3. save(path)   → persiste os dois artefatos em disco
        4. load(path)   → carrega os dois artefatos de disco

    Se o modelo não estiver treinado/carregado, predict() retorna zeros
    sem levantar exceção (modo fallback).

    O score NÃO é uma probabilidade calibrada. Ver model-card.md.
    """

    def __init__(
        self,
        contamination: float | None = None,
        n_estimators: int | None = None,
        random_state: int | None = None,
    ) -> None:
        self._contamination = contamination if contamination is not None else settings.model_contamination
        self._n_estimators = n_estimators if n_estimators is not None else settings.model_n_estimators
        self._random_state = random_state if random_state is not None else settings.model_random_state
        self._scaler: Any | None = None
        self._model: Any | None = None
        self._is_fitted: bool = False

    # ── Treino ────────────────────────────────────────────────────────────

    def fit(self, X: pd.DataFrame) -> "AnomalyDetector":
        """Treina o scaler e o IsolationForest sobre as features fornecidas.

        Args:
            X: DataFrame com as colunas de FEATURE_COLUMNS.

        Returns:
            self (para encadeamento).

        Raises:
            ImportError: Se sklearn não estiver disponível no ambiente.
        """
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        X_clean = self._select_and_validate(X)
        if len(X_clean) == 0:
            logger.warning("AnomalyDetector.fit: DataFrame vazio — modelo não treinado.")
            return self

        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X_clean)

        self._model = IsolationForest(
            contamination=self._contamination,
            n_estimators=self._n_estimators,
            random_state=self._random_state,
        )
        self._model.fit(X_scaled)
        self._is_fitted = True
        logger.info(
            "AnomalyDetector treinado: %d amostras, contamination=%.3f, "
            "n_estimators=%d, random_state=%d",
            len(X_clean),
            self._contamination,
            self._n_estimators,
            self._random_state,
        )
        return self

    # ── Predição ──────────────────────────────────────────────────────────

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Retorna anomaly_score normalizado por linha (0.0 = normal, 1.0 = anomalia forte).

        Fallback seguro: retorna zeros se o modelo não estiver treinado.

        Args:
            X: DataFrame com as colunas de FEATURE_COLUMNS.

        Returns:
            np.ndarray de float64 com shape (len(X),).

        Note:
            O score NÃO é uma probabilidade calibrada. É uma medida relativa
            de anomalia dentro do batch de predição.
        """
        if not self._is_fitted or self._model is None or self._scaler is None:
            logger.warning("AnomalyDetector.predict: modelo não treinado — retornando zeros.")
            return np.zeros(len(X), dtype=np.float64)

        X_clean = self._select_and_validate(X)
        if len(X_clean) == 0:
            return np.zeros(0, dtype=np.float64)

        X_scaled = self._scaler.transform(X_clean)

        # IsolationForest.score_samples retorna scores negativos: mais negativo = mais anômalo
        raw_scores: np.ndarray = self._model.score_samples(X_scaled)

        # Normaliza para [0, 1]: inverte o sinal e aplica min-max
        inverted = -raw_scores
        min_val, max_val = inverted.min(), inverted.max()
        if max_val - min_val < 1e-9:
            return np.zeros(len(X_clean), dtype=np.float64)

        normalized: np.ndarray = (inverted - min_val) / (max_val - min_val)
        return normalized.astype(np.float64)

    # ── Persistência ──────────────────────────────────────────────────────

    def save(self, directory: str | Path) -> dict[str, Path]:
        """Salva model e scaler em arquivos .joblib separados.

        Args:
            directory: Diretório onde salvar os artefatos.

        Returns:
            Dicionário com os caminhos {'model': Path, 'scaler': Path}.

        Raises:
            RuntimeError: Se o modelo não estiver treinado.
        """
        import joblib

        if not self._is_fitted:
            raise RuntimeError("Modelo não está treinado. Chame fit() antes de save().")

        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)

        version = settings.model_version
        model_path = path / f"anomaly_detector_{version}.joblib"
        scaler_path = path / f"scaler_{version}.joblib"

        joblib.dump(self._model, model_path)
        joblib.dump(self._scaler, scaler_path)

        logger.info("Modelo salvo: %s", model_path)
        logger.info("Scaler salvo: %s", scaler_path)
        return {"model": model_path, "scaler": scaler_path}

    @classmethod
    def load(cls, directory: str | Path, version: str | None = None) -> "AnomalyDetector":
        """Carrega model e scaler de arquivos .joblib.

        Args:
            directory: Diretório onde os artefatos estão salvos.
            version: Versão do modelo (usa settings.model_version se None).

        Returns:
            Instância de AnomalyDetector com modelo carregado.

        Raises:
            FileNotFoundError: Se os artefatos não existirem.
        """
        import joblib

        v = version or settings.model_version
        path = Path(directory)
        model_path = path / f"anomaly_detector_{v}.joblib"
        scaler_path = path / f"scaler_{v}.joblib"

        if not model_path.exists() or not scaler_path.exists():
            raise FileNotFoundError(
                f"Artefatos do modelo não encontrados em '{directory}' "
                f"(versão '{v}'). Execute scripts/train_model.py primeiro."
            )

        detector = cls()
        detector._model = joblib.load(model_path)
        detector._scaler = joblib.load(scaler_path)
        detector._is_fitted = True
        logger.info("Modelo carregado: %s", model_path)
        return detector

    # ── Helpers ───────────────────────────────────────────────────────────

    def _select_and_validate(self, X: pd.DataFrame) -> pd.DataFrame:
        """Seleciona colunas de features e preenche ausentes com 0."""
        missing = [c for c in FEATURE_COLUMNS if c not in X.columns]
        if missing:
            logger.warning("Colunas ausentes no DataFrame: %s — preenchendo com 0.", missing)
        result = X.copy()
        for col in missing:
            result[col] = 0.0
        return result[FEATURE_COLUMNS].fillna(0.0)

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted


# ── Instância global (lazy-loaded pela API) ────────────────────────────────

_global_detector: AnomalyDetector | None = None


def get_detector() -> AnomalyDetector:
    """Retorna a instância global do detector, carregando do disco se necessário.

    Se o artefato não existir, retorna um detector não treinado (fallback rules-only).
    """
    global _global_detector
    if _global_detector is not None:
        return _global_detector

    try:
        _global_detector = AnomalyDetector.load(settings.model_dir)
        logger.info("AnomalyDetector carregado do disco — modo híbrido ativo.")
    except FileNotFoundError:
        logger.info("Artefato de modelo não encontrado — operando em modo rules-only.")
        _global_detector = AnomalyDetector()  # não treinado → fallback

    return _global_detector
