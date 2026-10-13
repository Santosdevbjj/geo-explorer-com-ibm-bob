"""Gerador de logs sintéticos para o Sentinel.

Gera eventos de log reproduzíveis com seed fixo.
Injeta anomalias controláveis para treino e avaliação.

Categorias de evento:
    normal             → tráfego HTTP/auth legítimo e variado
    brute_force        → rajada de falhas de autenticação de um mesmo IP
    endpoint_scan      → varredura sistemática de endpoints HTTP
    traffic_spike      → pico de requisições de um IP em curto intervalo
    injection_attempt → SQL injection, path traversal ou XSS no request_path
    benign_similar     → casos limítrofes: falhas legítimas, user-agents incomuns
    invalid            → registros intencionalmente malformados (testes de validação)

AVISO: dados sintéticos não validam eficácia operacional em ambientes reais.
Parâmetros controlados neste gerador não refletem a distribuição de ataques
reais, que variam por organização, indústria e período. Use apenas para
desenvolvimento, testes e avaliação de pipeline.

Uso:
    python scripts/generate_synthetic_data.py
    python scripts/generate_synthetic_data.py --n-events 5000 --anomaly-rate 0.05 --seed 99
    python scripts/generate_synthetic_data.py --include-invalid
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

EVENT_TYPES = ["auth_attempt", "http_request", "dns_query", "network_flow"]
STATUSES = ["success", "failure", "blocked", "timeout"]
PROTOCOLS = ["TCP", "UDP", "HTTP", "HTTPS", "ICMP"]

EVENT_TYPE_WEIGHTS = [0.30, 0.45, 0.15, 0.10]
STATUS_WEIGHTS_NORMAL = [0.80, 0.12, 0.05, 0.03]
STATUS_WEIGHTS_BRUTE = [0.05, 0.90, 0.04, 0.01]

# Paths HTTP legítimos
NORMAL_PATHS = [
    "/api/v1/login",
    "/api/v1/users",
    "/api/v1/data",
    "/api/v1/logout",
    "/api/v1/products",
    "/api/v1/orders",
    "/health",
    "/metrics",
    "/static/main.css",
    "/favicon.ico",
]

# Endpoints sistematicamente varridos (scan)
SCAN_PATHS = [
    "/admin",
    "/admin/panel",
    "/wp-admin",
    "/wp-login.php",
    "/phpmyadmin",
    "/.env",
    "/.git/config",
    "/actuator",
    "/actuator/env",
    "/console",
    "/manager/html",
    "/server-status",
    "/.htaccess",
    "/config.php",
    "/backup.zip",
]

# Payloads de injeção
INJECTION_PATHS = [
    "/?q=1' OR '1'='1",
    "/?id=1 UNION SELECT null,username,password FROM users--",
    "/?search=<script>alert(document.cookie)</script>",
    "/?name=../../etc/passwd",
    "/?file=../../../../etc/shadow",
    "/?cmd=;ls -la",
    "/?url=file:///etc/passwd",
    "/?input=admin'--",
]

# User-agents normais
NORMAL_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) AppleWebKit/605.1.15",
]

# User-agents de scanner/ferramentas automatizadas
SCANNER_AGENTS = [
    "sqlmap/1.7.8#stable (https://sqlmap.org)",
    "Nikto/2.1.6",
    "nmap scripting engine",
    "python-requests/2.31.0",
    "curl/7.88.1",
    "masscan/1.3",
    "zgrab/0.x",
]

# User-agents borderline: automatizados mas não necessariamente maliciosos
BORDERLINE_AGENTS = [
    "python-requests/2.31.0",
    "curl/7.88.1",
    "Go-http-client/1.1",
    "Java/11.0.20",
    "axios/1.4.0",
]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _random_ip(rng: random.Random, private: bool = True) -> str:
    """Gera um endereço IPv4 aleatório."""
    if private:
        return f"192.168.{rng.randint(0, 254)}.{rng.randint(1, 254)}"
    return f"{rng.randint(1, 223)}.{rng.randint(0, 254)}.{rng.randint(0, 254)}.{rng.randint(1, 254)}"


def _new_event_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128)))


# ── Geradores por categoria ───────────────────────────────────────────────────


def _generate_normal_event(rng: random.Random, base_time: datetime) -> dict:
    """Evento de comportamento normal (tráfego legítimo variado)."""
    event_type = rng.choices(EVENT_TYPES, weights=EVENT_TYPE_WEIGHTS, k=1)[0]
    status = rng.choices(STATUSES, weights=STATUS_WEIGHTS_NORMAL, k=1)[0]
    ts = base_time + timedelta(seconds=rng.randint(0, 3600))

    event: dict = {
        "event_id": _new_event_id(rng),
        "timestamp": ts.isoformat(),
        "source_ip": _random_ip(rng),
        "dest_ip": _random_ip(rng, private=False),
        "dest_port": rng.choice([80, 443, 22, 53, 8080]),
        "protocol": rng.choices(PROTOCOLS, k=1)[0],
        "event_type": event_type,
        "status": status,
        "user_id": f"user_{rng.randint(1, 500)}",
        "payload_size_bytes": rng.randint(64, 8192),
        "metadata": {"label": "normal"},
    }

    if event_type == "http_request":
        event["request_path"] = rng.choice(NORMAL_PATHS)
        event["user_agent"] = rng.choice(NORMAL_AGENTS)

    return event


def _generate_brute_force_burst(
    rng: random.Random,
    base_time: datetime,
    source_ip: str,
    n: int,
) -> list[dict]:
    """Rajada de tentativas de autenticação falhas de um mesmo IP (brute force)."""
    events = []
    for i in range(n):
        ts = base_time + timedelta(seconds=i * rng.randint(1, 5))
        events.append(
            {
                "event_id": _new_event_id(rng),
                "timestamp": ts.isoformat(),
                "source_ip": source_ip,
                "dest_ip": _random_ip(rng, private=False),
                "dest_port": 443,
                "protocol": "HTTPS",
                "event_type": "auth_attempt",
                "status": rng.choices(STATUSES, weights=STATUS_WEIGHTS_BRUTE, k=1)[0],
                "user_id": f"user_{rng.randint(1, 100)}",
                "payload_size_bytes": rng.randint(128, 512),
                "metadata": {"label": "brute_force"},
            }
        )
    return events


def _generate_endpoint_scan_burst(
    rng: random.Random,
    base_time: datetime,
    source_ip: str,
    n: int,
) -> list[dict]:
    """Varredura sistemática de endpoints HTTP de um mesmo IP (endpoint scan)."""
    events = []
    paths = list(SCAN_PATHS)
    rng.shuffle(paths)
    for i in range(n):
        ts = base_time + timedelta(milliseconds=i * rng.randint(100, 800))
        events.append(
            {
                "event_id": _new_event_id(rng),
                "timestamp": ts.isoformat(),
                "source_ip": source_ip,
                "dest_ip": _random_ip(rng, private=False),
                "dest_port": rng.choice([80, 443, 8080, 8443]),
                "protocol": rng.choice(["HTTP", "HTTPS"]),
                "event_type": "http_request",
                "status": rng.choice(["failure", "blocked", "timeout"]),
                "user_id": None,
                "payload_size_bytes": rng.randint(64, 256),
                "request_path": paths[i % len(paths)],
                "user_agent": rng.choice(SCANNER_AGENTS),
                "metadata": {"label": "endpoint_scan"},
            }
        )
    return events


def _generate_traffic_spike_burst(
    rng: random.Random,
    base_time: datetime,
    source_ip: str,
    n: int,
) -> list[dict]:
    """Pico de requisições de um IP em curto intervalo (traffic spike).

    Evento deliberadamente ambíguo: pode ser DDoS, scraper ou carga legítima.
    A categoria é determinada pelo contexto e regras, não pelo evento isolado.
    """
    events = []
    for i in range(n):
        ts = base_time + timedelta(milliseconds=i * rng.randint(10, 200))
        events.append(
            {
                "event_id": _new_event_id(rng),
                "timestamp": ts.isoformat(),
                "source_ip": source_ip,
                "dest_ip": _random_ip(rng, private=False),
                "dest_port": rng.choice([80, 443]),
                "protocol": rng.choice(["HTTP", "HTTPS"]),
                "event_type": "http_request",
                "status": rng.choices(
                    ["success", "failure", "timeout"], weights=[0.6, 0.3, 0.1], k=1
                )[0],
                "user_id": None,
                "payload_size_bytes": rng.randint(64, 4096),
                "request_path": rng.choice(NORMAL_PATHS),
                "user_agent": rng.choice(SCANNER_AGENTS[:3]),
                "metadata": {"label": "traffic_spike"},
            }
        )
    return events


def _generate_injection_event(rng: random.Random, base_time: datetime) -> dict:
    """Evento com payload de injeção no request_path (SQL injection / path traversal / XSS)."""
    ts = base_time + timedelta(seconds=rng.randint(0, 3600))
    return {
        "event_id": _new_event_id(rng),
        "timestamp": ts.isoformat(),
        "source_ip": _random_ip(rng),
        "dest_ip": _random_ip(rng, private=False),
        "dest_port": 443,
        "protocol": "HTTPS",
        "event_type": "http_request",
        "status": rng.choice(["failure", "blocked"]),
        "user_id": None,
        "payload_size_bytes": rng.randint(512, 4096),
        "request_path": rng.choice(INJECTION_PATHS),
        "user_agent": rng.choice(SCANNER_AGENTS),
        "metadata": {"label": "injection_attempt"},
    }


def _generate_benign_similar_event(rng: random.Random, base_time: datetime) -> dict:
    """Evento benigno que superficialmente parece suspeito (caso limítrofe)."""
    scenario = rng.choice(["failed_logins", "automation_agent", "health_poller"])
    ts = base_time + timedelta(seconds=rng.randint(0, 3600))

    if scenario == "failed_logins":
        return {
            "event_id": _new_event_id(rng),
            "timestamp": ts.isoformat(),
            "source_ip": _random_ip(rng),
            "dest_ip": _random_ip(rng, private=False),
            "dest_port": 443,
            "protocol": "HTTPS",
            "event_type": "auth_attempt",
            "status": "failure",
            "user_id": f"user_{rng.randint(1, 500)}",
            "payload_size_bytes": rng.randint(128, 512),
            "metadata": {"label": "benign_similar", "scenario": "failed_logins"},
        }
    elif scenario == "automation_agent":
        return {
            "event_id": _new_event_id(rng),
            "timestamp": ts.isoformat(),
            "source_ip": _random_ip(rng),
            "dest_ip": _random_ip(rng, private=False),
            "dest_port": rng.choice([80, 443]),
            "protocol": rng.choice(["HTTP", "HTTPS"]),
            "event_type": "http_request",
            "status": "success",
            "user_id": f"svc_{rng.randint(1, 20)}",
            "payload_size_bytes": rng.randint(64, 1024),
            "request_path": rng.choice(NORMAL_PATHS),
            "user_agent": rng.choice(BORDERLINE_AGENTS),
            "metadata": {"label": "benign_similar", "scenario": "automation_agent"},
        }
    else:  # health_poller
        return {
            "event_id": _new_event_id(rng),
            "timestamp": ts.isoformat(),
            "source_ip": _random_ip(rng),
            "dest_ip": _random_ip(rng, private=False),
            "dest_port": 443,
            "protocol": "HTTPS",
            "event_type": "http_request",
            "status": "success",
            "user_id": None,
            "payload_size_bytes": rng.randint(64, 256),
            "request_path": "/health",
            "user_agent": rng.choice(BORDERLINE_AGENTS),
            "metadata": {"label": "benign_similar", "scenario": "health_poller"},
        }


def _generate_invalid_records(rng: random.Random, n: int) -> list[dict]:
    """Registros intencionalmente malformados para testes de validação de schema."""
    defects = [
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "source_ip": "999.999.999.999",
            "event_type": "http_request",
            "status": "success",
            "metadata": {"label": "invalid", "defect": "invalid_ip"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": "2025-01-15T10:00:00",
            "source_ip": "192.168.1.1",
            "event_type": "auth_attempt",
            "status": "failure",
            "metadata": {"label": "invalid", "defect": "missing_timezone"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "source_ip": "192.168.1.2",
            "event_type": "unknown_type",
            "status": "success",
            "metadata": {"label": "invalid", "defect": "unknown_event_type"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "source_ip": "192.168.1.3",
            "event_type": "http_request",
            "status": "success",
            "payload_size_bytes": -100,
            "metadata": {"label": "invalid", "defect": "negative_payload_size"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "source_ip": "192.168.1.4",
            "event_type": "network_flow",
            "status": "success",
            "dest_port": 99999,
            "metadata": {"label": "invalid", "defect": "port_out_of_range"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "source_ip": "192.168.1.5",
            "event_type": "auth_attempt",
            "status": "not_a_real_status",
            "metadata": {"label": "invalid", "defect": "invalid_status"},
        },
        {
            "event_id": _new_event_id(rng),
            "timestamp": datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC).isoformat(),
            "event_type": "http_request",
            "status": "success",
            "metadata": {"label": "invalid", "defect": "missing_source_ip"},
        },
        {
            "event_id": _new_event_id(rng),
            "source_ip": "192.168.1.6",
            "event_type": "dns_query",
            "status": "success",
            "metadata": {"label": "invalid", "defect": "missing_timestamp"},
        },
    ]
    return [defects[i % len(defects)] for i in range(n)]


# ── Orquestração ──────────────────────────────────────────────────────────────


def generate_events(
    n_events: int = 2000,
    anomaly_rate: float = 0.05,
    seed: int = 42,
    include_invalid: bool = False,
    n_invalid: int = 8,
) -> list[dict]:
    """Gera lista de eventos sintéticos com anomalias injetadas."""
    rng = random.Random(seed)  # nosec B311
    base_time = datetime(2025, 1, 15, 8, 0, 0, tzinfo=UTC)

    n_anomalies = max(5, int(n_events * anomaly_rate))
    n_normal = n_events - n_anomalies

    anomaly_categories = [
        "brute_force",
        "endpoint_scan",
        "traffic_spike",
        "injection",
        "benign_similar",
    ]
    per_category = n_anomalies // len(anomaly_categories)
    remainders = n_anomalies - per_category * len(anomaly_categories)

    category_counts = dict.fromkeys(anomaly_categories, per_category)
    for i in range(remainders):
        category_counts[anomaly_categories[i]] += 1

    events: list[dict] = []

    for _ in range(n_normal):
        events.append(_generate_normal_event(rng, base_time))

    bf_total = category_counts["brute_force"]
    burst_size = max(8, bf_total // max(1, bf_total // 15))
    injected = 0
    while injected < bf_total:
        count = min(burst_size, bf_total - injected)
        attacker_ip = _random_ip(rng)
        burst_ts = base_time + timedelta(minutes=rng.randint(0, 50))
        events.extend(_generate_brute_force_burst(rng, burst_ts, attacker_ip, count))
        injected += count

    es_total = category_counts["endpoint_scan"]
    scan_size = max(6, es_total // max(1, es_total // 12))
    injected = 0
    while injected < es_total:
        count = min(scan_size, es_total - injected)
        scanner_ip = _random_ip(rng, private=False)
        scan_ts = base_time + timedelta(minutes=rng.randint(0, 55))
        events.extend(_generate_endpoint_scan_burst(rng, scan_ts, scanner_ip, count))
        injected += count

    ts_total = category_counts["traffic_spike"]
    spike_size = max(10, ts_total // max(1, ts_total // 8))
    injected = 0
    while injected < ts_total:
        count = min(spike_size, ts_total - injected)
        spike_ip = _random_ip(rng, private=False)
        spike_ts = base_time + timedelta(minutes=rng.randint(0, 45))
        events.extend(_generate_traffic_spike_burst(rng, spike_ts, spike_ip, count))
        injected += count

    for _ in range(category_counts["injection"]):
        events.append(_generate_injection_event(rng, base_time))

    for _ in range(category_counts["benign_similar"]):
        events.append(_generate_benign_similar_event(rng, base_time))

    rng.shuffle(events)

    if include_invalid:
        n_invalid_clamped = min(n_invalid, 8)
        events.extend(_generate_invalid_records(rng, n_invalid_clamped))

    counts = {cat: category_counts[cat] for cat in anomaly_categories}
    logger.info(
        "Gerados %d eventos: %d normais, %d anômalos (%.1f%%) | "
        "brute_force=%d endpoint_scan=%d traffic_spike=%d injection=%d benign_similar=%d",
        len(events) - (n_invalid if include_invalid else 0),
        n_normal,
        n_anomalies,
        anomaly_rate * 100,
        counts["brute_force"],
        counts["endpoint_scan"],
        counts["traffic_spike"],
        counts["injection"],
        counts["benign_similar"],
    )
    if include_invalid:
        logger.info("Incluídos %d registros inválidos ao final.", min(n_invalid, 8))

    return events


def save_jsonl(events: list[dict], output_path: Path) -> None:
    """Salva eventos em formato JSONL (um JSON por linha)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    logger.info("Arquivo salvo: %s (%d registros)", output_path, len(events))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gerador de logs sintéticos do Sentinel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "AVISO: dados sintéticos não validam eficácia operacional em ambientes reais.\n"
            "Use apenas para desenvolvimento, testes e avaliação de pipeline."
        ),
    )
    parser.add_argument(
        "--n-events", type=int, default=2000, help="Total de eventos (padrão: 2000)"
    )
    parser.add_argument(
        "--anomaly-rate",
        type=float,
        default=0.05,
        help="Taxa de anomalias 0–1 (padrão: 0.05)",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Seed para reprodutibilidade (padrão: 42)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/synthetic/events.jsonl",
        help="Caminho de saída",
    )
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Inclui registros inválidos ao final para testes de validação",
    )
    parser.add_argument(
        "--n-invalid",
        type=int,
        default=8,
        help="Número de registros inválidos a incluir (máx 8, padrão: 8)",
    )
    args = parser.parse_args()

    if not 0.0 < args.anomaly_rate < 1.0:
        logger.error(
            "--anomaly-rate deve estar entre 0 e 1 (exclusivo). Recebido: %s",
            args.anomaly_rate,
        )
        sys.exit(1)

    if args.n_events < 10:
        logger.error("--n-events deve ser pelo menos 10. Recebido: %s", args.n_events)
        sys.exit(1)

    events = generate_events(
        n_events=args.n_events,
        anomaly_rate=args.anomaly_rate,
        seed=args.seed,
        include_invalid=args.include_invalid,
        n_invalid=args.n_invalid,
    )
    save_jsonl(events, Path(args.output))


if __name__ == "__main__":
    main()
