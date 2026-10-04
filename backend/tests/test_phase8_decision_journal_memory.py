"""R112C decision journal foundation and zero-write persistence boundary."""

from datetime import datetime, timezone

import pytest

from backend.medar.decision_journal import DecisionJournalEntry
from backend.medar.decision_journal_memory import DecisionJournalMemory, persist_decision_journal
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    entry = DecisionJournalEntry(
        entry_id="synthetic-decision-1", decision="choose synthetic option",
        options=("A", "B"), recommendation="A", chosen_option="A",
        expected_outcome="synthetic lower risk", observed_outcome="synthetic no change",
        recorded_at=NOW,
    )
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        source_reference="synthetic-decision-source-1", entry=entry,
        lesson="no demonstrated benefit", recorded_at=NOW,
    )
    values.update(changes)
    return DecisionJournalMemory(**values)


class SpyWriter:
    def __init__(self):
        self.writes = []

    def write(self, record):
        self.writes.append(record)


def test_journal_tracks_decision_options_outcomes_lesson_without_write_authority():
    memory = _memory()
    assert memory.entry.options == ("A", "B")
    assert memory.entry.expected_outcome == "synthetic lower risk"
    assert memory.entry.observed_outcome == "synthetic no change"
    assert memory.lesson == "no demonstrated benefit"
    assert memory.domain is DurableMemoryDomain.DECISION_JOURNAL
    assert memory.sensitivity is DurableSensitivity.SENSITIVE
    assert memory.session_only and not memory.persistence_authorized
    assert not memory.execution_authority
    assert memory.entry.decision not in repr(memory)


def test_sensitive_journal_persistence_blocks_before_store_side_effects():
    writer = SpyWriter()
    with pytest.raises(PermissionError, match="approved production encryption"):
        persist_decision_journal(_memory(), writer)
    assert writer.writes == []


@pytest.mark.parametrize("change", [
    {"source_reference": ""}, {"session_only": False},
    {"persistence_authorized": True}, {"execution_authority": True},
    {"domain": DurableMemoryDomain.BUSINESS},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"recorded_at": datetime(2026, 10, 4)},
])
def test_journal_rejects_weakened_scope_or_authority(change):
    with pytest.raises(ValueError):
        _memory(**change)


def test_journal_rejects_secret_like_lesson_and_unbounded_entry():
    with pytest.raises(PermissionError):
        _memory(lesson="api_key: synthetic")
    original = _memory().entry
    unbounded = DecisionJournalEntry(
        original.entry_id, "x" * 1025, original.options, original.recommendation,
        original.chosen_option, original.expected_outcome, original.observed_outcome, original.recorded_at,
    )
    with pytest.raises(ValueError):
        _memory(entry=unbounded)
