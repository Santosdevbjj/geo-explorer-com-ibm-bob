"""Testes unitários para scripts/generate_synthetic_data.py.

Cobre:
- Reprodutibilidade (mesmo seed → resultado idêntico)
- Compatibilidade com o schema LogEvent para eventos válidos
- Total de registros e taxa de anomalias
- Distribuição das categorias de anomalia
- Características estruturais de cada categoria
- Presença e limites dos campos numéricos
- Registros inválidos: existência e defeitos documentados
- Casos limítrofes: benign_similar com scenarios corretos

AVISO: estes testes verificam o comportamento do gerador, não a eficácia
operacional dos dados em ambientes reais.
"""

from __future__ import annotations

import json
import random
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.generate_synthetic_data import (
    INJECTION_PATHS,
    NORMAL_PATHS,
    SCAN_PATHS,
    _generate_benign_similar_event,
    _generate_brute_force_burst,
    _generate_endpoint_scan_burst,
    _generate_injection_event,
    _generate_invalid_records,
    _generate_traffic_spike_burst,
    _random_ip,
    generate_events,
    save_jsonl,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def base_time() -> datetime:
    return datetime(2025, 1, 15, 8, 0, 0, tzinfo=UTC)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(42)


@pytest.fixture
def small_events() -> list[dict]:
    """Conjunto pequeno de eventos (100) para testes de estrutura."""
    return generate_events(n_events=100, anomaly_rate=0.05, seed=42)


@pytest.fixture
def events_with_invalid() -> list[dict]:
    """Conjunto com registros inválidos ao final."""
    return generate_events(
        n_events=100, anomaly_rate=0.05, seed=42, include_invalid=True, n_invalid=8
    )


# ── Reprodutibilidade ─────────────────────────────────────────────────────────


class TestReproducibility:
    """Mesmo seed deve produzir resultado byte-a-byte idêntico."""

    def test_same_seed_same_result(self) -> None:
        a = generate_events(n_events=200, anomaly_rate=0.05, seed=7)
        b = generate_events(n_events=200, anomaly_rate=0.05, seed=7)
        assert a == b, "generate_events com mesmo seed deve ser determinístico"

    def test_different_seed_different_result(self) -> None:
        a = generate_events(n_events=200, anomaly_rate=0.05, seed=1)
        b = generate_events(n_events=200, anomaly_rate=0.05, seed=2)
        # Com 200 eventos é virtualmente impossível obter resultado idêntico
        assert a != b, "Seeds diferentes devem produzir sequências diferentes"

    def test_seed_param_respected(self) -> None:
        """Seed passado como argumento deve controlar o estado interno do RNG."""
        e1 = generate_events(n_events=50, seed=99)
        e2 = generate_events(n_events=50, seed=99)
        assert [e["event_id"] for e in e1] == [e["event_id"] for e in e2]


# ── Contagens e taxa de anomalias ─────────────────────────────────────────────


class TestCounts:
    def test_total_events_matches_n_events(self, small_events: list[dict]) -> None:
        assert len(small_events) == 100

    def test_anomaly_rate_approximate(self) -> None:
        """Taxa de anomalias deve ser próxima do valor solicitado (±2pp)."""
        events = generate_events(n_events=1000, anomaly_rate=0.10, seed=42)
        labels = [e["metadata"]["label"] for e in events]
        n_anomaly = sum(1 for lb in labels if lb != "normal")
        actual_rate = n_anomaly / len(events)
        assert abs(actual_rate - 0.10) < 0.02, (
            f"Taxa esperada ~10%, obtida {actual_rate:.2%}"
        )

    def test_include_invalid_adds_records(
        self, events_with_invalid: list[dict]
    ) -> None:
        """Com include_invalid=True o total deve ser 100 + 8 registros inválidos."""
        assert len(events_with_invalid) == 108

    def test_without_invalid_no_invalid_label(self, small_events: list[dict]) -> None:
        labels = [e["metadata"]["label"] for e in small_events]
        assert "invalid" not in labels

    def test_minimum_anomaly_floor(self) -> None:
        """Mesmo com rate muito baixo, deve haver pelo menos 5 anomalias."""
        events = generate_events(n_events=200, anomaly_rate=0.001, seed=42)
        labels = [e["metadata"]["label"] for e in events]
        n_anomaly = sum(1 for lb in labels if lb != "normal")
        assert n_anomaly >= 5


# ── Distribuição de categorias ────────────────────────────────────────────────


class TestCategoryDistribution:
    """Todas as 5 categorias de anomalia devem estar presentes."""

    ANOMALY_LABELS = {
        "brute_force",
        "endpoint_scan",
        "traffic_spike",
        "injection_attempt",
        "benign_similar",
    }

    def test_all_anomaly_categories_present(self) -> None:
        events = generate_events(n_events=500, anomaly_rate=0.10, seed=42)
        labels = {e["metadata"]["label"] for e in events}
        for expected in self.ANOMALY_LABELS:
            assert expected in labels, f"Categoria ausente: {expected}"

    def test_normal_label_present(self, small_events: list[dict]) -> None:
        labels = {e["metadata"]["label"] for e in small_events}
        assert "normal" in labels

    def test_no_unexpected_labels(self) -> None:
        expected_labels = self.ANOMALY_LABELS | {"normal"}
        events = generate_events(n_events=300, anomaly_rate=0.10, seed=42)
        unexpected = {
            e["metadata"]["label"]
            for e in events
            if e["metadata"]["label"] not in expected_labels
        }
        assert not unexpected, f"Labels inesperados: {unexpected}"


# ── Schema dos campos obrigatórios ────────────────────────────────────────────


class TestSchema:
    """Campos obrigatórios do LogEvent devem estar presentes nos eventos válidos."""

    REQUIRED_FIELDS = {
        "event_id",
        "timestamp",
        "source_ip",
        "event_type",
        "status",
        "metadata",
    }

    def test_required_fields_present(self, small_events: list[dict]) -> None:
        for i, event in enumerate(small_events):
            missing = self.REQUIRED_FIELDS - event.keys()
            assert not missing, f"Evento {i} faltando campos: {missing}"

    def test_event_id_is_uuid_format(self, small_events: list[dict]) -> None:
        import re

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        for event in small_events:
            assert uuid_pattern.match(event["event_id"]), (
                f"event_id inválido: {event['event_id']}"
            )

    def test_timestamp_has_timezone(self, small_events: list[dict]) -> None:
        """Todos os timestamps válidos devem ter offset de timezone (+HH:MM ou Z)."""
        for event in small_events:
            ts = event["timestamp"]
            has_tz = ts.endswith("Z") or "+" in ts or (ts.count("-") >= 3)
            assert has_tz, f"Timestamp sem timezone: {ts}"

    def test_event_type_valid_values(self, small_events: list[dict]) -> None:
        valid = {"auth_attempt", "http_request", "dns_query", "network_flow"}
        for event in small_events:
            assert event["event_type"] in valid, (
                f"event_type inválido: {event['event_type']}"
            )

    def test_status_valid_values(self, small_events: list[dict]) -> None:
        valid = {"success", "failure", "blocked", "timeout"}
        for event in small_events:
            assert event["status"] in valid, f"status inválido: {event['status']}"

    def test_dest_port_within_bounds(self, small_events: list[dict]) -> None:
        for event in small_events:
            port = event.get("dest_port")
            if port is not None:
                assert 1 <= port <= 65535, f"dest_port fora do intervalo: {port}"

    def test_payload_size_non_negative(self, small_events: list[dict]) -> None:
        for event in small_events:
            size = event.get("payload_size_bytes")
            if size is not None:
                assert size >= 0, f"payload_size_bytes negativo: {size}"

    def test_label_in_metadata(self, small_events: list[dict]) -> None:
        """Label deve estar sempre em metadata.label, nunca como campo de primeiro nível."""
        for event in small_events:
            assert "label" in event["metadata"], "label deve estar em metadata"
            assert "label" not in event or event.get("label") is None


# ── Características por categoria ─────────────────────────────────────────────


class TestBruteForce:
    def test_event_type_is_auth_attempt(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_brute_force_burst(rng, base_time, "10.0.0.1", 15)
        assert all(e["event_type"] == "auth_attempt" for e in burst)

    def test_all_same_source_ip(self, base_time: datetime, rng: random.Random) -> None:
        burst = _generate_brute_force_burst(rng, base_time, "10.0.0.1", 10)
        ips = {e["source_ip"] for e in burst}
        assert ips == {"10.0.0.1"}, (
            "Todos os eventos do burst devem ter o mesmo source_ip"
        )

    def test_mostly_failures(self, base_time: datetime, rng: random.Random) -> None:
        burst = _generate_brute_force_burst(rng, base_time, "10.0.0.1", 50)
        failures = sum(1 for e in burst if e["status"] == "failure")
        assert failures / len(burst) > 0.7, "Brute force deve ter maioria de failures"

    def test_label_is_brute_force(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_brute_force_burst(rng, base_time, "10.0.0.1", 5)
        assert all(e["metadata"]["label"] == "brute_force" for e in burst)

    def test_timestamps_all_after_base_time(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        """Todos os eventos do burst devem ter timestamp >= base_time."""
        from datetime import datetime as dt

        burst = _generate_brute_force_burst(rng, base_time, "10.0.0.1", 10)
        for e in burst:
            ts = dt.fromisoformat(e["timestamp"])
            assert ts >= base_time, f"Timestamp antes do base_time: {ts}"


class TestEndpointScan:
    def test_event_type_is_http_request(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_endpoint_scan_burst(rng, base_time, "203.0.113.1", 10)
        assert all(e["event_type"] == "http_request" for e in burst)

    def test_all_same_source_ip(self, base_time: datetime, rng: random.Random) -> None:
        burst = _generate_endpoint_scan_burst(rng, base_time, "203.0.113.1", 10)
        ips = {e["source_ip"] for e in burst}
        assert ips == {"203.0.113.1"}

    def test_paths_are_scan_paths(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_endpoint_scan_burst(
            rng, base_time, "203.0.113.1", len(SCAN_PATHS)
        )
        paths = {e["request_path"] for e in burst}
        assert paths.issubset(set(SCAN_PATHS)), (
            f"Paths inesperados: {paths - set(SCAN_PATHS)}"
        )

    def test_label_is_endpoint_scan(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_endpoint_scan_burst(rng, base_time, "203.0.113.1", 5)
        assert all(e["metadata"]["label"] == "endpoint_scan" for e in burst)

    def test_mostly_non_success_status(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_endpoint_scan_burst(rng, base_time, "203.0.113.1", 40)
        non_success = sum(1 for e in burst if e["status"] != "success")
        assert non_success / len(burst) > 0.5, (
            "Scan deve ter maioria de respostas não-sucesso"
        )


class TestTrafficSpike:
    def test_event_type_is_http_request(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_traffic_spike_burst(rng, base_time, "203.0.113.2", 20)
        assert all(e["event_type"] == "http_request" for e in burst)

    def test_all_same_source_ip(self, base_time: datetime, rng: random.Random) -> None:
        burst = _generate_traffic_spike_burst(rng, base_time, "203.0.113.2", 20)
        ips = {e["source_ip"] for e in burst}
        assert ips == {"203.0.113.2"}

    def test_timestamps_very_close(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        """Intervalo total do spike não pode ultrapassar o intervalo máximo (n * 200ms)."""
        from datetime import datetime as dt

        n = 20
        burst = _generate_traffic_spike_burst(rng, base_time, "203.0.113.2", n)
        t_first = dt.fromisoformat(burst[0]["timestamp"])
        t_last = dt.fromisoformat(burst[-1]["timestamp"])
        elapsed_seconds = (t_last - t_first).total_seconds()
        # n * 200ms = 4s máximo; toleramos 10s por margem de segurança
        assert elapsed_seconds < 10, f"Spike muito longo: {elapsed_seconds:.1f}s"

    def test_paths_are_normal(self, base_time: datetime, rng: random.Random) -> None:
        burst = _generate_traffic_spike_burst(rng, base_time, "203.0.113.2", 20)
        for e in burst:
            assert e["request_path"] in NORMAL_PATHS

    def test_label_is_traffic_spike(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        burst = _generate_traffic_spike_burst(rng, base_time, "203.0.113.2", 5)
        assert all(e["metadata"]["label"] == "traffic_spike" for e in burst)


class TestInjection:
    def test_event_type_is_http_request(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        event = _generate_injection_event(rng, base_time)
        assert event["event_type"] == "http_request"

    def test_path_is_injection_path(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        for _ in range(20):
            event = _generate_injection_event(rng, base_time)
            assert event["request_path"] in INJECTION_PATHS

    def test_label_is_injection_attempt(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        event = _generate_injection_event(rng, base_time)
        assert event["metadata"]["label"] == "injection_attempt"

    def test_status_is_failure_or_blocked(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        statuses = set()
        for _ in range(30):
            statuses.add(_generate_injection_event(rng, base_time)["status"])
        assert statuses.issubset({"failure", "blocked"})


class TestBenignSimilar:
    VALID_SCENARIOS = {"failed_logins", "automation_agent", "health_poller"}

    def test_label_is_benign_similar(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        for _ in range(10):
            event = _generate_benign_similar_event(rng, base_time)
            assert event["metadata"]["label"] == "benign_similar"

    def test_scenario_field_present(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        for _ in range(10):
            event = _generate_benign_similar_event(rng, base_time)
            assert "scenario" in event["metadata"]

    def test_scenario_values_are_known(
        self, base_time: datetime, rng: random.Random
    ) -> None:
        for _ in range(30):
            event = _generate_benign_similar_event(rng, base_time)
            assert event["metadata"]["scenario"] in self.VALID_SCENARIOS

    def test_all_scenarios_reachable(self) -> None:
        """Com seed diferente e N amostras suficientes, todos os scenarios devem aparecer."""
        rng = random.Random(123)
        base_time = datetime(2025, 1, 15, 8, 0, 0, tzinfo=UTC)
        scenarios = set()
        for _ in range(100):
            e = _generate_benign_similar_event(rng, base_time)
            scenarios.add(e["metadata"]["scenario"])
        assert scenarios == self.VALID_SCENARIOS

    def test_failed_logins_scenario_has_user_id(self, base_time: datetime) -> None:
        """Cenário failed_logins representa usuário real — user_id não pode ser None."""
        rng = random.Random(0)
        found = False
        for _ in range(50):
            event = _generate_benign_similar_event(rng, base_time)
            if event["metadata"]["scenario"] == "failed_logins":
                assert event["user_id"] is not None
                found = True
                break
        assert found, "Cenário 'failed_logins' não apareceu em 50 tentativas"

    def test_health_poller_path_is_health(self, base_time: datetime) -> None:
        rng = random.Random(5)
        found = False
        for _ in range(100):
            event = _generate_benign_similar_event(rng, base_time)
            if event["metadata"]["scenario"] == "health_poller":
                assert event["request_path"] == "/health"
                found = True
                break
        assert found, "Cenário 'health_poller' não apareceu em 100 tentativas"


# ── Registros inválidos ───────────────────────────────────────────────────────


class TestInvalidRecords:
    KNOWN_DEFECTS = {
        "invalid_ip",
        "missing_timezone",
        "unknown_event_type",
        "negative_payload_size",
        "port_out_of_range",
        "invalid_status",
        "missing_source_ip",
        "missing_timestamp",
    }

    def test_generates_correct_count(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        assert len(records) == 8

    def test_all_defects_present(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        defects = {r["metadata"]["defect"] for r in records}
        assert defects == self.KNOWN_DEFECTS

    def test_label_is_invalid(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        assert all(r["metadata"]["label"] == "invalid" for r in records)

    def test_invalid_ip_record_has_bad_ip(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        bad_ip_rec = next(r for r in records if r["metadata"]["defect"] == "invalid_ip")
        # Um IP 999.x.x.x é sintaticamente inválido
        assert bad_ip_rec["source_ip"] == "999.999.999.999"

    def test_missing_timezone_has_no_offset(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        tz_rec = next(
            r for r in records if r["metadata"]["defect"] == "missing_timezone"
        )
        ts = tz_rec["timestamp"]
        has_tz = ts.endswith("Z") or "+" in ts
        assert not has_tz, f"Esperava timestamp sem timezone, obteve: {ts}"

    def test_negative_payload_is_negative(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        neg_rec = next(
            r for r in records if r["metadata"]["defect"] == "negative_payload_size"
        )
        assert neg_rec["payload_size_bytes"] < 0

    def test_port_out_of_range_exceeds_65535(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 8)
        port_rec = next(
            r for r in records if r["metadata"]["defect"] == "port_out_of_range"
        )
        assert port_rec["dest_port"] > 65535

    def test_cycles_when_n_less_than_8(self, rng: random.Random) -> None:
        records = _generate_invalid_records(rng, 3)
        assert len(records) == 3

    def test_invalid_records_at_end_of_batch(
        self, events_with_invalid: list[dict]
    ) -> None:
        """Registros inválidos devem estar nas últimas 8 posições (não embaralhados)."""
        last_8 = events_with_invalid[-8:]
        labels = {e["metadata"]["label"] for e in last_8}
        assert labels == {"invalid"}, (
            f"Esperava só 'invalid' no final, obteve: {labels}"
        )


# ── Integração: save_jsonl ────────────────────────────────────────────────────


class TestSaveJsonl:
    def test_file_created(self, small_events: list[dict]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_events.jsonl"
            save_jsonl(small_events, out)
            assert out.exists()

    def test_line_count_matches(self, small_events: list[dict]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_events.jsonl"
            save_jsonl(small_events, out)
            lines = out.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == len(small_events)

    def test_each_line_is_valid_json(self, small_events: list[dict]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_events.jsonl"
            save_jsonl(small_events, out)
            for i, line in enumerate(
                out.read_text(encoding="utf-8").strip().splitlines()
            ):
                parsed = json.loads(line)
                assert isinstance(parsed, dict), f"Linha {i} não é um objeto JSON"

    def test_round_trip_preserves_events(self, small_events: list[dict]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test_events.jsonl"
            save_jsonl(small_events, out)
            loaded = [
                json.loads(line)
                for line in out.read_text(encoding="utf-8").strip().splitlines()
            ]
        assert loaded == small_events

    def test_creates_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "deep" / "events.jsonl"
            events = generate_events(n_events=10, seed=1)
            save_jsonl(events, out)
            assert out.exists()


# ── Helpers internos ──────────────────────────────────────────────────────────


class TestHelpers:
    def test_random_ip_private_range(self) -> None:
        rng = random.Random(0)
        for _ in range(50):
            ip = _random_ip(rng, private=True)
            assert ip.startswith("192.168."), f"IP privado fora do range: {ip}"

    def test_random_ip_public_range(self) -> None:
        rng = random.Random(0)
        for _ in range(50):
            ip = _random_ip(rng, private=False)
            assert not ip.startswith("192.168."), f"IP público parece privado: {ip}"

    def test_random_ip_format(self) -> None:
        rng = random.Random(0)
        for _ in range(50):
            ip = _random_ip(rng)
            parts = ip.split(".")
            assert len(parts) == 4
            assert all(p.isdigit() for p in parts)


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_minimum_n_events(self) -> None:
        """n_events=10 deve funcionar sem erro."""
        events = generate_events(n_events=10, anomaly_rate=0.5, seed=42)
        assert len(events) == 10

    def test_high_anomaly_rate(self) -> None:
        """Taxa de 90% não pode quebrar a geração."""
        events = generate_events(n_events=100, anomaly_rate=0.9, seed=42)
        assert len(events) == 100

    def test_low_anomaly_rate(self) -> None:
        """Taxa de 1% não pode quebrar a geração."""
        events = generate_events(n_events=100, anomaly_rate=0.01, seed=42)
        assert len(events) == 100

    def test_n_invalid_capped_at_8(self) -> None:
        """n_invalid=20 deve ser limitado a 8 internamente."""
        events = generate_events(
            n_events=50, seed=42, include_invalid=True, n_invalid=20
        )
        invalid_count = sum(1 for e in events if e["metadata"]["label"] == "invalid")
        assert invalid_count == 8, (
            f"Esperava 8 registros inválidos, obteve {invalid_count}"
        )

    def test_events_are_shuffled(self) -> None:
        """Eventos devem estar embaralhados (não todos agrupados por label).

        Com 500 eventos e 20% de anomalias (100 eventos anômalos), é estatisticamente
        improvável que nenhuma anomalia apareça nos primeiros 100 eventos se houve shuffle.
        Verificamos os 200 primeiros (40% do total) para ter margem confortável.
        """
        events = generate_events(n_events=500, anomaly_rate=0.20, seed=42)
        labels = [e["metadata"]["label"] for e in events]
        first_200_labels = set(labels[:200])
        assert len(first_200_labels) > 1, (
            f"Eventos não parecem estar embaralhados — apenas {first_200_labels} nos primeiros 200"
        )

    def test_event_ids_are_unique(self) -> None:
        events = generate_events(n_events=500, anomaly_rate=0.05, seed=42)
        ids = [e["event_id"] for e in events]
        assert len(ids) == len(set(ids)), "event_ids duplicados encontrados"
