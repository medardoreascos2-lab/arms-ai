"""R31A tests for the immutable historical dataset registry."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path

import pytest

from backend.research import (
    DatasetCertificationStatus,
    DatasetConflictError,
    DatasetFileFormat,
    DatasetIntegrityError,
    DatasetUnavailableError,
    DatasetVerificationStatus,
    DatasetWindow,
    HistoricalDatasetRegistration,
    HistoricalDatasetRegistry,
)


NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def write_csv(path, rows=3):
    lines = ["time,open,high,low,close,volume"]
    for index in range(rows):
        lines.append(
            f"2026-10-0{index + 1}T14:30:00Z,100,102,99,101,{10 + index}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registration(path, **changes):
    values = dict(
        dataset_id="nq-dec26-1m-one-week",
        instrument="NQ",
        contract="NQ DEC26",
        timeframe="1m",
        session_template="CME US Index Futures ETH",
        starts_at=NOW - timedelta(days=7),
        ends_at=NOW,
        source="ninjatrader-historical-export:v1",
        window=DatasetWindow.ONE_WEEK,
        file_format=DatasetFileFormat.CSV,
        expected_bar_count=3,
        expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        certification_status=DatasetCertificationStatus.CERTIFIED,
        certification_reference="certification:nq-dec26:2026-10-04",
    )
    values.update(changes)
    return HistoricalDatasetRegistration(**values)


def test_registers_available_csv_with_exact_file_evidence(tmp_path):
    source = tmp_path / "bars.csv"
    digest = write_csv(source)
    registry = HistoricalDatasetRegistry((tmp_path,))

    result = registry.register(registration(source), path=source, registered_at=NOW)

    assert result.inserted and not result.duplicate
    assert result.record.sha256 == digest
    assert result.record.bar_count == 3
    assert result.record.byte_count == source.stat().st_size
    assert result.record.path == source.resolve()
    assert registry.get(result.record.dataset_id) == result.record
    assert registry.verify(result.record.dataset_id).status is DatasetVerificationStatus.VERIFIED
    assert registry.require_verified(result.record.dataset_id) == result.record
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False


def test_missing_or_outside_source_is_never_registered(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.csv"
    write_csv(outside)
    registry = HistoricalDatasetRegistry((allowed,))

    with pytest.raises(DatasetUnavailableError, match="outside allowed roots"):
        registry.register(registration(outside), path=outside, registered_at=NOW)
    with pytest.raises(DatasetUnavailableError, match="unavailable"):
        registry.register(
            registration(outside), path=allowed / "missing.csv", registered_at=NOW,
        )
    assert registry.list() == ()


@pytest.mark.parametrize("field", ("expected_sha256", "expected_bar_count"))
def test_registration_rejects_declared_evidence_that_does_not_match_file(
    tmp_path, field,
):
    source = tmp_path / "bars.csv"
    write_csv(source)
    item = registration(source)
    item = replace(
        item,
        **({field: "0" * 64} if field == "expected_sha256" else {field: 99}),
    )

    with pytest.raises(DatasetIntegrityError, match="does not match"):
        HistoricalDatasetRegistry((tmp_path,)).register(
            item, path=source, registered_at=NOW,
        )


def test_duplicate_is_idempotent_and_dataset_id_conflict_is_rejected(tmp_path):
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    write_csv(first_path)
    write_csv(second_path, rows=4)
    registry = HistoricalDatasetRegistry((tmp_path,))
    first = registry.register(registration(first_path), path=first_path, registered_at=NOW)
    duplicate = registry.register(
        registration(first_path), path=first_path, registered_at=NOW + timedelta(hours=1),
    )

    assert duplicate.duplicate and duplicate.record == first.record
    with pytest.raises(DatasetConflictError, match="different immutable content"):
        registry.register(
            registration(
                second_path,
                expected_bar_count=4,
                expected_sha256=hashlib.sha256(second_path.read_bytes()).hexdigest(),
            ),
            path=second_path,
            registered_at=NOW,
        )
    assert len(registry.list()) == 1


@pytest.mark.parametrize("window", tuple(DatasetWindow))
def test_supports_each_required_research_window(tmp_path, window):
    source = tmp_path / f"{window.value}.csv"
    write_csv(source)
    registry = HistoricalDatasetRegistry((tmp_path,))
    item = registration(source, dataset_id=f"dataset-{window.value.lower()}", window=window)

    record = registry.register(item, path=source, registered_at=NOW).record

    assert registry.list(window=window) == (record,)


def test_jsonl_registration_counts_only_real_json_objects(tmp_path):
    source = tmp_path / "bars.jsonl"
    source.write_text('{"close":"101","time":"t1"}\n{"close":"102","time":"t2"}\n')
    item = registration(
        source,
        dataset_id="nq-jsonl",
        file_format=DatasetFileFormat.JSONL,
        expected_bar_count=2,
    )

    result = HistoricalDatasetRegistry((tmp_path,)).register(
        item, path=source, registered_at=NOW,
    )

    assert result.record.bar_count == 2


@pytest.mark.parametrize(
    "content",
    (
        '{"time":"t1","time":"t2"}\n',
        '{"close":NaN,"time":"t1"}\n',
        '[{"time":"t1"}]\n',
    ),
)
def test_jsonl_rejects_non_object_or_non_strict_rows(tmp_path, content):
    source = tmp_path / "invalid.jsonl"
    source.write_text(content, encoding="utf-8")
    item = registration(
        source,
        dataset_id="invalid-jsonl",
        file_format=DatasetFileFormat.JSONL,
        expected_bar_count=1,
    )

    with pytest.raises(DatasetIntegrityError):
        HistoricalDatasetRegistry((tmp_path,)).register(
            item, path=source, registered_at=NOW,
        )


@pytest.mark.parametrize(
    "content",
    (
        "time,open\n2026-10-01,1,unexpected\n",
        "time,time\n2026-10-01,1\n",
        "time,open\n",
    ),
)
def test_invalid_or_empty_csv_is_rejected_without_registration(tmp_path, content):
    source = tmp_path / "invalid.csv"
    source.write_text(content, encoding="utf-8")
    registry = HistoricalDatasetRegistry((tmp_path,))
    item = registration(
        source,
        expected_bar_count=1,
        expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    )

    with pytest.raises(DatasetIntegrityError):
        registry.register(item, path=source, registered_at=NOW)
    assert registry.list() == ()


def test_modified_source_fails_closed_without_mutating_registered_record(tmp_path):
    source = tmp_path / "bars.csv"
    write_csv(source)
    registry = HistoricalDatasetRegistry((tmp_path,))
    record = registry.register(registration(source), path=source, registered_at=NOW).record
    original_hash = record.record_hash

    source.write_text(source.read_text(encoding="utf-8") + "2026-10-05,1,1,1,1,1\n")
    verification = registry.verify(record.dataset_id)

    assert verification.status is DatasetVerificationStatus.CHANGED
    assert "SHA256_CHANGED" in verification.reasons
    assert "BAR_COUNT_CHANGED" in verification.reasons
    with pytest.raises(DatasetIntegrityError, match="not currently verified"):
        registry.require_verified(record.dataset_id)
    assert registry.get(record.dataset_id).record_hash == original_hash


def test_deleted_source_reports_missing_and_never_substitutes_data(tmp_path):
    source = tmp_path / "bars.csv"
    write_csv(source)
    registry = HistoricalDatasetRegistry((tmp_path,))
    record = registry.register(registration(source), path=source, registered_at=NOW).record
    source.unlink()

    verification = registry.verify(record.dataset_id)

    assert verification.status is DatasetVerificationStatus.MISSING
    assert verification.reasons == ("SOURCE_UNAVAILABLE",)
    with pytest.raises(DatasetIntegrityError):
        registry.require_verified(record.dataset_id)


def test_certification_claim_requires_evidence_and_records_are_frozen(tmp_path):
    source = tmp_path / "bars.csv"
    write_csv(source)
    with pytest.raises(ValueError, match="certification_reference"):
        registration(source, certification_reference=None)
    with pytest.raises(ValueError, match="cannot claim"):
        registration(
            source,
            certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        )
    uncertified = registration(
        source,
        certification_status=DatasetCertificationStatus.AVAILABLE_UNCERTIFIED,
        certification_reference=None,
    )
    record = HistoricalDatasetRegistry((tmp_path,)).register(
        uncertified, path=source, registered_at=NOW,
    ).record
    with pytest.raises(FrozenInstanceError):
        record.bar_count = 99


def test_contract_rejects_naive_time_and_invalid_ranges(tmp_path):
    source = tmp_path / "bars.csv"
    write_csv(source)
    with pytest.raises(ValueError, match="timezone-aware"):
        registration(source, starts_at=datetime(2026, 10, 1))
    with pytest.raises(ValueError, match="must precede"):
        registration(source, starts_at=NOW, ends_at=NOW)


def test_registry_has_no_execution_or_data_generation_dependency():
    import backend.research.dataset_registry as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "backend.execution", "broker", "enterlong", "entershort",
        "submit_order", "requests", "httpx", "random", "faker",
    )
    assert all(token not in source for token in forbidden)
    assert HistoricalDatasetRegistry.execution_authorized is False
    assert HistoricalDatasetRegistry.production_mutation_authorized is False
    assert HistoricalDatasetRegistry.canonical_admin_authorized is False
