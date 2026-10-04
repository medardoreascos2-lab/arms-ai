"""R111A NQ research stays source-linked and nonexecuting."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.futures_research_memory import (
    FuturesInstrument, FuturesResearchMemory, ResearchObservationMode,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _record(**changes):
    values = dict(
        instrument=FuturesInstrument.NQ, tenant_id="tenant-a", owner_id="owner-a",
        session_id="session-a", source_reference="synthetic-study-1",
        dataset_reference="synthetic-bars-1", observation_mode=ResearchObservationMode.SYNTHETIC_TEST,
        market_regime="synthetic range", setup="synthetic sweep", decision="hold",
        result="no synthetic order", risk_observation="risk gate remained closed",
        evidence="synthetic bar trace", observed_at=NOW,
    )
    values.update(changes)
    return FuturesResearchMemory(**values)


def test_nq_record_tracks_research_fields_without_execution_authority():
    record = _record()
    assert record.domain is DurableMemoryDomain.NQ
    assert record.sensitivity is DurableSensitivity.SENSITIVE
    assert record.dataset_reference == "synthetic-bars-1"
    assert record.observation_mode is ResearchObservationMode.SYNTHETIC_TEST
    assert record.session_only
    assert not record.broker_authority and not record.paper_execution_authority and not record.live_execution_authority
    assert record.result not in repr(record)


def test_nq_research_rejects_missing_dataset_secret_and_execution_claim():
    with pytest.raises(ValueError):
        _record(dataset_reference="")
    with pytest.raises(PermissionError):
        _record(evidence="api_key: synthetic")
    with pytest.raises(ValueError):
        _record(broker_authority=True)
    with pytest.raises(ValueError):
        _record(sensitivity=DurableSensitivity.PUBLIC)
    with pytest.raises(PermissionError):
        _record(observation_mode=ResearchObservationMode.PAPER_OBSERVED)
