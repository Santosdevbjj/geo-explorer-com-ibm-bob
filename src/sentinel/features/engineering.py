"""Engenharia de atributos do Sentinel.

Transforma eventos brutos (LogEvent) em features numéricas
para uso pelo modelo ML (detection/model.py) e pelas regras (detection/rules.py).

PRINCÍPIOS:
- Determinismo: mesmo input + mesmo window_seconds → mesmo output (sem estado externo).
- Sem vazamento de target: nenhuma feature usa metadata.label nem campos ausentes
  em inferência (ex: user_id não é usada diretamente porque pode ser None).
- Disponibilidade em inferência: todas as features são computáveis a partir de
  campos que chegam em tempo real (source_ip, timestamp, event_type, status,
  request_path, user_agent, payload_size_bytes).
- Separação descrição/causalidade: as features descrevem padrões observáveis;
  a interpretação causal (ex: "alta failure_ratio → brute force") é responsabilidade
  das regras e do analista, não desta camada.

Features por janela deslizante (source_ip × window_start):
    Grupo auth:
        auth_failure_rate       taxa de falhas de autenticação (auth_attempt failures / total)
        auth_failure_count      contagem absoluta de auth failures
    Grupo HTTP:
        request_count           total de http_request na janela
        unique_paths            caminhos únicos acessados
        req_per_second          densidade de requisições (req_count / window_seconds)
        scan_path_hits          requisições a paths tipicamente varridos por scanners
    Grupo falhas:
        failure_ratio           proporção de eventos com status failure ou blocked
        error_count             contagem absoluta de failure + blocked
        timeout_ratio           proporção de timeouts
    Grupo payload:
        payload_size_mean       tamanho médio do payload em bytes
        payload_size_std        desvio padrão do tamanho do payload
    Grupo temporal:
        inter_event_mean_ms     média do intervalo entre eventos consecutivos (ms)
        inter_event_min_ms      menor intervalo entre eventos (ms) — sinal de spike
    Grupo user-agent:
        scanner_agent_ratio     proporção de eventos com user-agent de scanner conhecido

HIPÓTESES (a validar empiricamente, não afirmadas como fato):
- Alta auth_failure_rate + baixa req_per_second pode indicar brute force lento.
- Alta req_per_second + baixo inter_event_min_ms pode indicar traffic spike automatizado.
- Alto unique_paths + alto scan_path_hits pode indicar varredura de endpoints.
- Alto scanner_agent_ratio é indicativo de ferramenta automatizada (não necessariamente maliciosa).

LIMITAÇÕES:
- Janela deslizante O(n²) por IP: adequada para batches analíticos, não para streaming de alto volume.
- Features são calculadas por source_ip: ataques distribuídos (diferentes IPs) não são capturados aqui.
- scanner_agent_ratio usa lista estática de substrings: pode gerar falsos positivos em user-agents legítimos.
- inter_event_min_ms = 0 indica eventos simultâneos ou resolução de timestamp insuficiente.
"""

from __future__ import annotations

import re
from datetime import timedelta

import numpy as np
import pandas as pd

from sentinel.schemas import EventStatus, EventType, LogEvent


# ── Padrões de user-agent de scanner ──────────────────────────────────────────
# Lista conservadora: apenas ferramentas explicitamente identificadas como scanners.
# Não inclui user-agents ambíguos como "python-requests" ou "curl" que têm uso legítimo.
_SCANNER_UA_PATTERN = re.compile(
    r"sqlmap|nikto|nmap|masscan|zgrab|dirbuster|gobuster|wfuzz|hydra|medusa"
    r"|burpsuite|zaproxy|nuclei|metasploit|nessus|openvas",
    re.IGNORECASE,
)

# Paths típicos de varredura automatizada
_SCAN_PATHS: frozenset[str] = frozenset({
    "/admin", "/admin/panel", "/wp-admin", "/wp-login.php",
    "/phpmyadmin", "/.env", "/.git/config", "/actuator",
    "/actuator/env", "/console", "/manager/html", "/server-status",
    "/.htaccess", "/config.php", "/backup.zip",
})


# ── Schema esperado de saída ───────────────────────────────────────────────────

FEATURE_COLUMNS: list[str] = [
    # Identificação
    "source_ip",
    "window_start",
    # Autenticação
    "auth_failure_rate",
    "auth_failure_count",
    # HTTP
    "request_count",
    "unique_paths",
    "req_per_second",
    "scan_path_hits",
    # Falhas
    "failure_ratio",
    "error_count",
    "timeout_ratio",
    # Payload
    "payload_size_mean",
    "payload_size_std",
    # Temporal
    "inter_event_mean_ms",
    "inter_event_min_ms",
    # User-agent
    "scanner_agent_ratio",
]


# ── Funções auxiliares ─────────────────────────────────────────────────────────


def _is_scanner_agent(ua: str | None) -> bool:
    """Retorna True se o user-agent corresponde a um scanner conhecido."""
    if not ua:
        return False
    return bool(_SCANNER_UA_PATTERN.search(ua))


def _is_scan_path(path: str | None) -> bool:
    """Retorna True se o path é típico de varredura automatizada."""
    if not path:
        return False
    return path in _SCAN_PATHS


def _compute_inter_event_stats(timestamps_ms: list[float]) -> tuple[float, float]:
    """Calcula média e mínimo dos intervalos entre eventos consecutivos em ms.

    Args:
        timestamps_ms: Lista de timestamps em milissegundos, já ordenados.

    Returns:
        (mean_ms, min_ms). Retorna (0.0, 0.0) se menos de 2 eventos.
    """
    if len(timestamps_ms) < 2:
        return 0.0, 0.0
    diffs = [
        timestamps_ms[i + 1] - timestamps_ms[i]
        for i in range(len(timestamps_ms) - 1)
    ]
    return float(np.mean(diffs)), float(min(diffs))


# ── Extração principal ────────────────────────────────────────────────────────


def extract_features(
    events: list[LogEvent],
    window_seconds: int = 300,
) -> pd.DataFrame:
    """Extrai features por (source_ip, window_start) em janela deslizante.

    Para cada evento como âncora, calcula features sobre todos os eventos
    do mesmo source_ip dentro de [anchor_ts, anchor_ts + window_seconds].

    Args:
        events: Lista de eventos validados (LogEvent). Não usa metadata.label.
        window_seconds: Tamanho da janela deslizante em segundos.

    Returns:
        DataFrame com uma linha por (source_ip, window_start) sem duplicatas.
        Colunas: ver FEATURE_COLUMNS.

    Note:
        Esta função não usa metadata.label nem nenhum campo ausente em inferência.
        É determinística: mesmo input produz mesmo output.
    """
    if not events:
        return _empty_features_df()

    rows = [
        {
            "source_ip": str(e.source_ip),
            "timestamp": e.timestamp,
            "event_type": e.event_type.value,
            "status": e.status.value,
            "request_path": e.request_path,
            "user_agent": e.user_agent,
            "payload_size_bytes": e.payload_size_bytes if e.payload_size_bytes is not None else 0,
        }
        for e in events
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    window = timedelta(seconds=window_seconds)
    feature_rows: list[dict] = []

    for ip, group in df.groupby("source_ip", sort=False):
        group = group.sort_values("timestamp").reset_index(drop=True)
        timestamps = group["timestamp"].tolist()
        ts_ms = [t.timestamp() * 1000 for t in timestamps]

        for i, anchor_ts in enumerate(timestamps):
            window_end = anchor_ts + window
            mask = (group["timestamp"] >= anchor_ts) & (group["timestamp"] <= window_end)
            wdf = group[mask]

            n_total = len(wdf)
            if n_total == 0:
                continue

            # ── Autenticação ──────────────────────────────────────────────────
            is_auth = wdf["event_type"] == EventType.AUTH_ATTEMPT.value
            is_failure = wdf["status"] == EventStatus.FAILURE.value
            auth_failure_count = int((is_auth & is_failure).sum())
            auth_failure_rate = auth_failure_count / n_total

            # ── HTTP ──────────────────────────────────────────────────────────
            is_http = wdf["event_type"] == EventType.HTTP_REQUEST.value
            request_count = int(is_http.sum())
            unique_paths = int(wdf.loc[is_http, "request_path"].dropna().nunique())
            req_per_second = request_count / max(window_seconds, 1)
            scan_path_hits = int(
                wdf["request_path"].dropna().apply(_is_scan_path).sum()
            )

            # ── Falhas ────────────────────────────────────────────────────────
            is_failed = wdf["status"].isin([
                EventStatus.FAILURE.value, EventStatus.BLOCKED.value
            ])
            is_timeout = wdf["status"] == EventStatus.TIMEOUT.value
            error_count = int(is_failed.sum())
            failure_ratio = error_count / n_total
            timeout_ratio = int(is_timeout.sum()) / n_total

            # ── Payload ───────────────────────────────────────────────────────
            payload = wdf["payload_size_bytes"].astype(float)
            payload_size_mean = float(payload.mean())
            payload_size_std = float(payload.std(ddof=0)) if n_total > 1 else 0.0

            # ── Temporal ─────────────────────────────────────────────────────
            window_ts_ms = [ts_ms[j] for j, t in enumerate(timestamps) if anchor_ts <= t <= window_end]
            inter_mean_ms, inter_min_ms = _compute_inter_event_stats(sorted(window_ts_ms))

            # ── User-agent ────────────────────────────────────────────────────
            n_scanner = int(wdf["user_agent"].apply(_is_scanner_agent).sum())
            scanner_agent_ratio = n_scanner / n_total

            feature_rows.append({
                "source_ip": ip,
                "window_start": anchor_ts,
                "auth_failure_rate": auth_failure_rate,
                "auth_failure_count": float(auth_failure_count),
                "request_count": float(request_count),
                "unique_paths": float(unique_paths),
                "req_per_second": req_per_second,
                "scan_path_hits": float(scan_path_hits),
                "failure_ratio": failure_ratio,
                "error_count": float(error_count),
                "timeout_ratio": timeout_ratio,
                "payload_size_mean": payload_size_mean,
                "payload_size_std": payload_size_std,
                "inter_event_mean_ms": inter_mean_ms,
                "inter_event_min_ms": inter_min_ms,
                "scanner_agent_ratio": scanner_agent_ratio,
            })

    if not feature_rows:
        return _empty_features_df()

    result = pd.DataFrame(feature_rows)
    result = result.drop_duplicates(subset=["source_ip", "window_start"]).reset_index(drop=True)
    # Garante ordem canônica de colunas
    return result[FEATURE_COLUMNS]


def _empty_features_df() -> pd.DataFrame:
    """Retorna DataFrame vazio com o schema canônico de features."""
    return pd.DataFrame(columns=FEATURE_COLUMNS)


# ── Análise exploratória ───────────────────────────────────────────────────────
# Funções auxiliares usadas pelo notebook 01_exploratory_analysis.ipynb.
# Todas operam sobre listas de dicts (eventos brutos) ou DataFrames,
# nunca sobre LogEvent, para independência do schema Pydantic no notebook.


def compute_volume_stats(df_raw: pd.DataFrame) -> dict:
    """Estatísticas de volume e completude sobre o DataFrame de eventos brutos.

    Args:
        df_raw: DataFrame com colunas mínimas: event_id, timestamp, source_ip,
                event_type, status. Coluna metadata.label NÃO é usada.

    Returns:
        Dicionário com: total_events, unique_ips, unique_event_types,
        duplicate_event_ids, missing_per_column (dict), date_range_hours.

    Note:
        metadata.label é excluído da análise para evitar uso acidental
        de informação do target durante a exploração de features.
    """
    total = len(df_raw)
    unique_ips = df_raw["source_ip"].nunique() if "source_ip" in df_raw.columns else 0
    unique_types = df_raw["event_type"].nunique() if "event_type" in df_raw.columns else 0

    # Duplicatas de event_id
    dup_count = 0
    if "event_id" in df_raw.columns:
        dup_count = int(df_raw["event_id"].duplicated().sum())

    # Valores ausentes por coluna (excluindo metadata e label)
    exclude = {"metadata", "label"}
    missing = {
        col: int(df_raw[col].isna().sum())
        for col in df_raw.columns
        if col not in exclude and df_raw[col].isna().any()
    }

    # Intervalo temporal
    date_range_hours = 0.0
    if "timestamp" in df_raw.columns:
        ts = pd.to_datetime(df_raw["timestamp"], utc=True, errors="coerce")
        ts_valid = ts.dropna()
        if len(ts_valid) >= 2:
            delta = ts_valid.max() - ts_valid.min()
            date_range_hours = delta.total_seconds() / 3600

    return {
        "total_events": total,
        "unique_ips": unique_ips,
        "unique_event_types": unique_types,
        "duplicate_event_ids": dup_count,
        "missing_per_column": missing,
        "date_range_hours": round(date_range_hours, 2),
    }


def compute_request_frequency(df_raw: pd.DataFrame, window_minutes: int = 5) -> pd.DataFrame:
    """Calcula frequência de requisições por IP em janelas fixas de tempo.

    Usa apenas event_type='http_request' e source_ip.
    NÃO usa metadata.label.

    Args:
        df_raw: DataFrame com colunas source_ip, timestamp, event_type.
        window_minutes: Largura da janela em minutos.

    Returns:
        DataFrame com (source_ip, window, request_count), ordenado por request_count desc.
    """
    if df_raw.empty or "timestamp" not in df_raw.columns:
        return pd.DataFrame(columns=["source_ip", "window", "request_count"])

    http = df_raw[df_raw["event_type"] == "http_request"].copy()
    if http.empty:
        return pd.DataFrame(columns=["source_ip", "window", "request_count"])

    http["timestamp"] = pd.to_datetime(http["timestamp"], utc=True, errors="coerce")
    http = http.dropna(subset=["timestamp"])
    http["window"] = http["timestamp"].dt.floor(f"{window_minutes}min")

    result = (
        http.groupby(["source_ip", "window"], observed=True)
        .size()
        .reset_index(name="request_count")
        .sort_values("request_count", ascending=False)
        .reset_index(drop=True)
    )
    return result


def compute_error_rate_by_type(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Calcula taxa de erro por event_type.

    Error = status in {'failure', 'blocked'}.
    NÃO usa metadata.label.

    Returns:
        DataFrame com (event_type, total, errors, error_rate).
    """
    if df_raw.empty or "event_type" not in df_raw.columns:
        return pd.DataFrame(columns=["event_type", "total", "errors", "error_rate"])

    df = df_raw.copy()
    df["is_error"] = df["status"].isin(["failure", "blocked"])
    result = (
        df.groupby("event_type", observed=True)
        .agg(total=("is_error", "count"), errors=("is_error", "sum"))
        .reset_index()
    )
    result["error_rate"] = result["errors"] / result["total"].clip(lower=1)
    return result.sort_values("error_rate", ascending=False).reset_index(drop=True)


def compute_endpoint_diversity(df_raw: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Calcula diversidade de endpoints: frequência de cada request_path.

    NÃO usa metadata.label.

    Returns:
        DataFrame com (request_path, count, pct) para os top_n paths.
    """
    if df_raw.empty or "request_path" not in df_raw.columns:
        return pd.DataFrame(columns=["request_path", "count", "pct"])

    paths = df_raw["request_path"].dropna()
    if paths.empty:
        return pd.DataFrame(columns=["request_path", "count", "pct"])

    counts = paths.value_counts().head(top_n).reset_index()
    counts.columns = pd.Index(["request_path", "count"])
    counts["pct"] = counts["count"] / counts["count"].sum()
    return counts


def compute_temporal_repetition(df_raw: pd.DataFrame, window_minutes: int = 1) -> pd.DataFrame:
    """Detecta IPs com padrão de repetição temporal intensa.

    Retorna IPs que enviaram eventos em múltiplas janelas de window_minutes,
    com o coeficiente de variação (CV) do volume por janela como indicador
    de regularidade (CV baixo → volume uniforme = mais suspeito).

    NÃO usa metadata.label.

    Returns:
        DataFrame com (source_ip, n_windows, mean_events, cv) ordenado por n_windows desc.
    """
    if df_raw.empty or "timestamp" not in df_raw.columns:
        return pd.DataFrame(columns=["source_ip", "n_windows", "mean_events", "cv"])

    df = df_raw.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp", "source_ip"])
    df["window"] = df["timestamp"].dt.floor(f"{window_minutes}min")

    per_window = (
        df.groupby(["source_ip", "window"], observed=True)
        .size()
        .reset_index(name="count")
    )

    result = (
        per_window.groupby("source_ip", observed=True)["count"]
        .agg(n_windows="count", mean_events="mean", std_events="std")
        .reset_index()
    )
    result["std_events"] = result["std_events"].fillna(0.0)
    result["cv"] = result["std_events"] / result["mean_events"].clip(lower=1e-9)
    result = result.drop(columns=["std_events"])
    return result.sort_values("n_windows", ascending=False).reset_index(drop=True)
