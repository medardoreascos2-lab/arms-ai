from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.research.provenance import ProvenanceConflictError, ResearchProvenanceRecord, ResearchProvenanceRegistry

NOW = datetime(2026, 10, 3, 16, tzinfo=timezone.utc)


def record(identifier: str = "result-1") -> ResearchProvenanceRecord:
    return ResearchProvenanceRecord(identifier, "a"*64, ("b"*64, "c"*64), "d"*64, "e"*64,
                                    "f"*40, 42, (("mode", "walk-forward"), ("version", "1")), NOW)


def test_record_contains_every_reconstruction_input_and_no_execution_authority() -> None:
    item = record()
    document = item.document()
    assert document["dataset_hashes"] == ["b"*64, "c"*64]
    assert document["strategy_hash"] == "d"*64
    assert document["parameter_hash"] == "e"*64
    assert document["code_commit"] == "f"*40
    assert document["random_seed"] == 42
    assert document["config"] == {"mode": "walk-forward", "version": "1"}
    assert item.reconstructable is True
    assert item.execution_authorized is False


def test_provenance_hash_is_deterministic() -> None:
    assert record().provenance_hash == record().provenance_hash


def test_registry_is_idempotent_for_identical_record() -> None:
    registry = ResearchProvenanceRegistry()
    first = registry.register(record())
    second = registry.register(record())
    assert first is second
    assert registry.list() == (first,)


def test_registry_rejects_identity_reuse_with_different_evidence() -> None:
    registry = ResearchProvenanceRegistry()
    registry.register(record())
    with pytest.raises(ProvenanceConflictError):
        registry.register(replace(record(), random_seed=43))


@pytest.mark.parametrize("change", [
    {"dataset_hashes": ()}, {"dataset_hashes": ("b"*64, "b"*64)},
    {"code_commit": "f"*39}, {"random_seed": -1}, {"config": ()},
    {"config": (("version", "1"), ("mode", "walk-forward"))},
])
def test_missing_or_ambiguous_reconstruction_inputs_are_rejected(change) -> None:
    with pytest.raises(ValueError):
        replace(record(), **change)


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(record(), created_at=datetime(2026, 10, 3))


def test_registry_lists_records_in_stable_identity_order() -> None:
    registry = ResearchProvenanceRegistry()
    registry.register(record("z-result"))
    registry.register(record("a-result"))
    assert [item.result_id for item in registry.list()] == ["a-result", "z-result"]
