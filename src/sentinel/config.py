"""Configuração centralizada do Sentinel via variáveis de ambiente.

Uso:
    from sentinel.config import settings
    print(settings.api_port)
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações do Sentinel carregadas do ambiente / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ambiente
    sentinel_env: str = Field(default="development", alias="SENTINEL_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_secret_key: str = Field(default="change-me-in-production", alias="API_SECRET_KEY")

    # Caminhos de dados
    data_raw_dir: str = Field(default="data/raw", alias="DATA_RAW_DIR")
    data_processed_dir: str = Field(default="data/processed", alias="DATA_PROCESSED_DIR")
    data_synthetic_dir: str = Field(default="data/synthetic", alias="DATA_SYNTHETIC_DIR")

    # Modelos
    model_dir: str = Field(default="models", alias="MODEL_DIR")
    model_version: str = Field(default="v1", alias="MODEL_VERSION")
    model_contamination: float = Field(default=0.05, alias="MODEL_CONTAMINATION")
    model_n_estimators: int = Field(default=100, alias="MODEL_N_ESTIMATORS")
    model_random_state: int = Field(default=42, alias="MODEL_RANDOM_STATE")

    # API — segurança e limites
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    max_batch_size: int = Field(default=10_000, alias="MAX_BATCH_SIZE")

    # Limiares de detecção
    alert_score_threshold: float = Field(default=0.6, alias="ALERT_SCORE_THRESHOLD")
    rule_min_attempts: int = Field(default=5, alias="RULE_MIN_ATTEMPTS")

    # MCP
    mcp_enabled: bool = Field(default=False, alias="MCP_ENABLED")
    mcp_host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(default=9000, alias="MCP_PORT")

    # Monitoramento / drift
    drift_reference_path: str = Field(
        default="data/processed/reference_distribution.json",
        alias="DRIFT_REFERENCE_PATH",
    )
    drift_alert_threshold: float = Field(default=0.1, alias="DRIFT_ALERT_THRESHOLD")


settings = Settings()
