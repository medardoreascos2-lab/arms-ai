"""R86D MEDAR durable memory provenance tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance


def _provenance(**overrides):
    values = dict(
        source_id="request-1", origin=MemoryOrigin.OBSERVED,
        recorded_at=datetime.now(timezone.utc), tenant_id="tenant-1",
        user_id="user-1", context_id="conversation-1", confidence=0.8,
    )
    values.update(overrides)
    return MemoryProvenance(**values)


def test_provenance_records_source_time_scope_confidence_and_origin():
    record = _provenance()
    assert record.source_id == "request-1"
    assert record.origin is MemoryOrigin.OBSERVED
    assert record.tenant_id == "tenant-1"
    assert record.user_id == "user-1"
    assert record.context_id == "conversation-1"
    assert record.confidence == 0.8


def test_all_required_origins_are_explicit():
    assert tuple(item.value for item in MemoryOrigin) == ("OBSERVED", "INFERRED", "IMPORTED")


def test_provenance_rejects_naive_time_and_invalid_confidence():
    with pytest.raises(ValueError, match="timezone-aware"):
        _provenance(recorded_at=datetime.now())
    with pytest.raises(ValueError, match="confidence"):
        _provenance(confidence=-0.1)
