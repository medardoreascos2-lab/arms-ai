"""R110A explicit technical evidence categories and session bounds."""

from datetime import datetime, timezone

import pytest

from backend.medar.technical_memory import TechnicalMemoryKind, TechnicalSessionMemory


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = dict(tenant_id="tenant-a", owner_id="owner-a", session_id="session-a")


def test_all_technical_categories_preserve_source_without_write_authority():
    memory = TechnicalSessionMemory(**SCOPE)
    for index, kind in enumerate(TechnicalMemoryKind):
        entry = memory.add(kind, f"synthetic {kind.value.lower()} evidence", f"source-{index}", observed_at=NOW)
        assert entry.kind is kind
        assert entry.source_reference == f"source-{index}"
        assert not entry.persistence_authorized and not entry.execution_authority
        assert entry.content not in repr(entry)
    assert len(memory.snapshot(**SCOPE)) == len(TechnicalMemoryKind)


def test_technical_memory_rejects_secret_duplicate_overflow_and_cross_scope():
    memory = TechnicalSessionMemory(**SCOPE, max_entries=1)
    with pytest.raises(PermissionError):
        memory.add(TechnicalMemoryKind.BUG, "api_key: synthetic", "source-1", observed_at=NOW)
    memory.add(TechnicalMemoryKind.BUG, "synthetic fault", "source-1", observed_at=NOW)
    with pytest.raises(ValueError):
        memory.add(TechnicalMemoryKind.ROOT_CAUSE, "synthetic root cause", "source-2", observed_at=NOW)
    with pytest.raises(PermissionError):
        memory.snapshot(tenant_id="tenant-b", owner_id="owner-a", session_id="session-a")
    assert len(memory.snapshot(**SCOPE)) == 1
    duplicate_memory = TechnicalSessionMemory(**SCOPE, max_entries=2)
    duplicate_memory.add(TechnicalMemoryKind.BUG, "synthetic fault", "source-1", observed_at=NOW)
    with pytest.raises(ValueError, match="already recorded"):
        duplicate_memory.add(TechnicalMemoryKind.BUG, "changed synthetic fault", "source-1", observed_at=NOW)
