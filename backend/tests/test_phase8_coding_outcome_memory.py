"""R110B coding outcome fields remain scoped and nonauthoritative."""

from datetime import datetime, timezone

import pytest

from backend.medar.coding_outcome_memory import CodingOutcomeMemory, CodingOutcomeStatus


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _outcome(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        source_reference="conversation-1/turn-4", task="synthetic migration",
        approach="apply scoped fix", files=("backend/medar/example.py",),
        tests=("pytest synthetic: passed",), status=CodingOutcomeStatus.SUCCESS,
        root_cause="schema mismatch", lesson="verify migration checksum",
        observed_at=NOW,
    )
    values.update(changes)
    return CodingOutcomeMemory(**values)


def test_outcome_carries_task_approach_files_tests_status_cause_and_lesson():
    outcome = _outcome()
    assert outcome.task == "synthetic migration"
    assert outcome.approach == "apply scoped fix"
    assert outcome.files == ("backend/medar/example.py",)
    assert outcome.tests == ("pytest synthetic: passed",)
    assert outcome.status is CodingOutcomeStatus.SUCCESS
    assert outcome.root_cause == "schema mismatch"
    assert outcome.lesson == "verify migration checksum"
    assert outcome.session_only and not outcome.persistence_authorized
    assert not outcome.code_modification_authority
    assert outcome.task not in repr(outcome) and outcome.lesson not in repr(outcome)


def test_outcome_rejects_missing_evidence_secret_or_authority_claim():
    with pytest.raises(ValueError):
        _outcome(lesson="")
    with pytest.raises(PermissionError):
        _outcome(root_cause="api_key: synthetic")
    with pytest.raises(ValueError):
        _outcome(files=("x" * 241,))
    with pytest.raises(ValueError):
        _outcome(tests=("x",) * 101)
    with pytest.raises(ValueError):
        _outcome(code_modification_authority=True)
    with pytest.raises(ValueError):
        _outcome(tests=())
