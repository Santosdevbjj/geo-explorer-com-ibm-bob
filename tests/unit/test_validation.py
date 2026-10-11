"""Testes unitários — src/sentinel/data/validation.py"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que src/ está no path quando rodado diretamente
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from sentinel.data.validation import validate_batch
from tests.fixtures.conftest import (
    make_auth_event,
    make_http_event,
)


# ── Batch totalmente válido ────────────────────────────────────────────────


class TestValidBatch:
    def test_passed_is_true(self, valid_batch: list[dict]) -> None:
        report = validate_batch(valid_batch)
        assert report.passed is True

    def test_total_equals_input(self, valid_batch: list[dict]) -> None:
        report = validate_batch(valid_batch)
        assert report.total_records == len(valid_batch)

    def test_all_valid(self, valid_batch: list[dict]) -> None:
        report = validate_batch(valid_batch)
        assert report.valid_records == len(valid_batch)
        assert report.invalid_records == 0

    def test_no_duplicates(self, valid_batch: list[dict]) -> None:
        report = validate_batch(valid_batch)
        assert report.duplicate_ids == []

    def test_no_missing_fields(self, valid_batch: list[dict]) -> None:
        report = validate_batch(valid_batch)
        assert report.missing_fields_summary == {}


# ── Duplicatas ─────────────────────────────────────────────────────────────


class TestDuplicates:
    def test_detects_duplicate_id(self, batch_with_duplicate: list[dict]) -> None:
        report = validate_batch(batch_with_duplicate)
        assert "evt-dup" in report.duplicate_ids

    def test_passed_is_false_with_duplicate(self, batch_with_duplicate: list[dict]) -> None:
        report = validate_batch(batch_with_duplicate)
        assert report.passed is False

    def test_duplicate_counted_once(self) -> None:
        """Mesmo ID aparecendo 3 vezes deve ser listado uma única vez."""
        batch = [make_auth_event(event_id="evt-x") for _ in range(3)]
        report = validate_batch(batch)
        assert report.duplicate_ids.count("evt-x") == 1


# ── Registros inválidos ────────────────────────────────────────────────────


class TestInvalidRecords:
    def test_detects_missing_required_fields(self, batch_with_invalid: list[dict]) -> None:
        report = validate_batch(batch_with_invalid)
        assert report.invalid_records >= 1

    def test_passed_is_false_with_invalid(self, batch_with_invalid: list[dict]) -> None:
        report = validate_batch(batch_with_invalid)
        assert report.passed is False

    def test_invalid_record_has_details(self, batch_with_invalid: list[dict]) -> None:
        report = validate_batch(batch_with_invalid)
        assert len(report.invalid_record_details) >= 1
        detail = report.invalid_record_details[0]
        assert len(detail.errors) >= 1

    def test_valid_records_not_affected(self, batch_with_invalid: list[dict]) -> None:
        """Os registros válidos do batch devem ser contados corretamente."""
        report = validate_batch(batch_with_invalid)
        # 3 registros no batch; 1 é inválido → 2 válidos
        assert report.valid_records == 2

    def test_missing_field_tracked_in_summary(self, batch_with_invalid: list[dict]) -> None:
        report = validate_batch(batch_with_invalid)
        assert len(report.missing_fields_summary) >= 1


# ── Timestamp sem timezone ─────────────────────────────────────────────────


class TestTimestampValidation:
    def test_timestamp_without_timezone_is_invalid(
        self, batch_without_timezone: list[dict]
    ) -> None:
        report = validate_batch(batch_without_timezone)
        assert report.invalid_records == 1
        assert report.passed is False

    def test_timestamp_with_utc_is_valid(self) -> None:
        event = make_auth_event(event_id="evt-tz")
        event["timestamp"] = "2025-06-01T10:00:00+00:00"
        report = validate_batch([event])
        assert report.valid_records == 1


# ── Batch vazio ────────────────────────────────────────────────────────────


class TestEmptyBatch:
    def test_empty_batch_passes(self) -> None:
        report = validate_batch([])
        assert report.total_records == 0
        assert report.passed is True

    def test_empty_batch_has_zero_counts(self) -> None:
        report = validate_batch([])
        assert report.valid_records == 0
        assert report.invalid_records == 0


# ── IP inválido ────────────────────────────────────────────────────────────


class TestIPValidation:
    def test_invalid_source_ip_rejected(self) -> None:
        event = make_auth_event(event_id="evt-badip")
        event["source_ip"] = "999.999.999.999"
        report = validate_batch([event])
        assert report.invalid_records == 1

    def test_ipv6_source_ip_accepted(self) -> None:
        event = make_auth_event(event_id="evt-ipv6")
        event["source_ip"] = "2001:db8::1"
        report = validate_batch([event])
        assert report.valid_records == 1


# ── Porta fora do intervalo ────────────────────────────────────────────────


class TestPortValidation:
    def test_port_zero_rejected(self) -> None:
        event = make_auth_event(event_id="evt-port0")
        event["dest_port"] = 0
        report = validate_batch([event])
        assert report.invalid_records == 1

    def test_port_65536_rejected(self) -> None:
        event = make_auth_event(event_id="evt-port-high")
        event["dest_port"] = 65536
        report = validate_batch([event])
        assert report.invalid_records == 1

    def test_port_443_accepted(self) -> None:
        event = make_auth_event(event_id="evt-port-ok")
        event["dest_port"] = 443
        report = validate_batch([event])
        assert report.valid_records == 1
