"""R31G tests for the append-only research challenger registry."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.research.backtest_runner import ResearchParameterSet
from backend.research.challenger_registry import (
    ChallengerConflictError,
    ChallengerStatus,
    ChallengerTransitionError,
    ProductionReferenceDefinition,
    PromotionHistoryEntry,
    StrategyChallengerRecord,
    StrategyChallengerRegistry,
)


UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def parameters(risk: int = 1) -> ResearchParameterSet:
    return ResearchParameterSet.from_mapping({"risk_units": risk, "signal": "v1"})


def registry() -> StrategyChallengerRegistry:
    return StrategyChallengerRegistry(
        ProductionReferenceDefinition(
            strategy_id="prod-v8",
            strategy_hash="a" * 64,
            parameters=parameters(),
            evidence_ids=("v8-freeze",),
            registered_at=T0,
        )
    )


def register(item: StrategyChallengerRegistry, *, strategy_id: str = "candidate-1"):
    return item.register_research(
        strategy_id=strategy_id,
        strategy_hash="b" * 64,
        parameters=parameters(2),
        evidence_ids=("backtest-1", "dataset-1"),
        registered_at=T0 + timedelta(days=1),
        reason="RESEARCH_EVIDENCE_REGISTERED",
    )


def assert_no_authority(value) -> None:
    assert value.execution_authorized is False
    assert value.paper_execution_authorized is False
    assert value.live_execution_authorized is False
    assert value.production_mutation_authorized is False


def test_production_reference_is_imported_read_only_and_has_no_authority():
    item = registry()
    production = item.production_reference()

    assert production.status is ChallengerStatus.PRODUCTION_REFERENCE
    assert production.strategy_id == "prod-v8"
    assert production.promotion_history[0].reason == "PRODUCTION_REFERENCE_IMPORTED_READ_ONLY"
    assert item.history("prod-v8") == (production,)
    assert_no_authority(item)
    assert_no_authority(production)
    with pytest.raises(FrozenInstanceError):
        production.status = ChallengerStatus.RESEARCH


def test_research_cannot_overwrite_or_transition_production_reference():
    item = registry()

    with pytest.raises(ChallengerConflictError, match="cannot overwrite"):
        item.register_research(
            strategy_id="prod-v8",
            strategy_hash="b" * 64,
            parameters=parameters(2),
            evidence_ids=("research-1",),
            registered_at=T0 + timedelta(days=1),
            reason="ATTEMPTED_OVERWRITE",
        )
    with pytest.raises(ChallengerTransitionError, match="read-only"):
        item.transition(
            "prod-v8",
            ChallengerStatus.CHALLENGER,
            evidence_ids=("gate-1",),
            reason="ATTEMPTED_TRANSITION",
            occurred_at=T0 + timedelta(days=1),
        )

    assert item.production_reference().strategy_hash == "a" * 64
    assert len(item.history("prod-v8")) == 1


def test_registration_stores_hash_parameters_evidence_status_and_history():
    item = registry()
    result = register(item)
    record = result.record

    assert result.inserted is True
    assert result.duplicate is False
    assert record.strategy_hash == "b" * 64
    assert record.parameters == parameters(2)
    assert record.evidence_ids == ("backtest-1", "dataset-1")
    assert record.status is ChallengerStatus.RESEARCH
    assert record.revision == 0
    assert record.previous_record_hash is None
    assert len(record.hash) == 64
    assert len(record.promotion_history[0].hash) == 64
    assert_no_authority(record)


def test_exact_registration_retry_is_idempotent_but_conflict_is_rejected():
    item = registry()
    first = register(item)
    duplicate = register(item)

    assert duplicate.inserted is False
    assert duplicate.duplicate is True
    assert duplicate.record is first.record
    assert len(item.history("candidate-1")) == 1

    with pytest.raises(ChallengerConflictError, match="different immutable"):
        item.register_research(
            strategy_id="candidate-1",
            strategy_hash="c" * 64,
            parameters=parameters(3),
            evidence_ids=("backtest-2",),
            registered_at=T0 + timedelta(days=1),
            reason="CONFLICT",
        )


def test_allowed_transitions_append_hash_chained_revisions_and_evidence():
    item = registry()
    research = register(item).record
    challenger = item.transition(
        research.strategy_id,
        ChallengerStatus.CHALLENGER,
        evidence_ids=("oos-pass",),
        reason="OOS_VALIDATED",
        occurred_at=T0 + timedelta(days=2),
    )
    paper = item.transition(
        research.strategy_id,
        ChallengerStatus.PAPER_CHALLENGER,
        evidence_ids=("human-paper-approval", "stress-pass"),
        reason="AUTHORIZED_FOR_ISOLATED_PAPER_EVALUATION",
        occurred_at=T0 + timedelta(days=3),
    )

    assert [record.status for record in item.history(research.strategy_id)] == [
        ChallengerStatus.RESEARCH,
        ChallengerStatus.CHALLENGER,
        ChallengerStatus.PAPER_CHALLENGER,
    ]
    assert challenger.previous_record_hash == research.hash
    assert paper.previous_record_hash == challenger.hash
    assert paper.evidence_ids == (
        "backtest-1",
        "dataset-1",
        "human-paper-approval",
        "oos-pass",
        "stress-pass",
    )
    for previous, current in zip(paper.promotion_history, paper.promotion_history[1:]):
        assert current.previous_event_hash == previous.hash
        assert current.from_status is previous.to_status
    assert_no_authority(paper)


@pytest.mark.parametrize(
    ("initial", "target"),
    (
        (ChallengerStatus.RESEARCH, ChallengerStatus.PAPER_CHALLENGER),
        (ChallengerStatus.RESEARCH, ChallengerStatus.PROMOTION_CANDIDATE),
        (ChallengerStatus.RESEARCH, ChallengerStatus.PRODUCTION_REFERENCE),
        (ChallengerStatus.CHALLENGER, ChallengerStatus.RESEARCH),
        (ChallengerStatus.CHALLENGER, ChallengerStatus.PRODUCTION_REFERENCE),
        (ChallengerStatus.PAPER_CHALLENGER, ChallengerStatus.CHALLENGER),
        (ChallengerStatus.PAPER_CHALLENGER, ChallengerStatus.PROMOTION_CANDIDATE),
    ),
)
def test_unauthorized_transitions_fail_without_mutating_history(initial, target):
    item = registry()
    record = register(item).record
    if initial is ChallengerStatus.CHALLENGER:
        record = item.transition(
            record.strategy_id,
            initial,
            evidence_ids=("gate-1",),
            reason="GATE_PASSED",
            occurred_at=T0 + timedelta(days=2),
        )
    elif initial is ChallengerStatus.PAPER_CHALLENGER:
        record = item.transition(
            record.strategy_id,
            ChallengerStatus.CHALLENGER,
            evidence_ids=("gate-1",),
            reason="GATE_PASSED",
            occurred_at=T0 + timedelta(days=2),
        )
        record = item.transition(
            record.strategy_id,
            initial,
            evidence_ids=("paper-approval",),
            reason="PAPER_APPROVED",
            occurred_at=T0 + timedelta(days=3),
        )
    before = item.history(record.strategy_id)

    with pytest.raises(ChallengerTransitionError, match="not allowed"):
        item.transition(
            record.strategy_id,
            target,
            evidence_ids=("bad-transition",),
            reason="UNAUTHORIZED",
            occurred_at=T0 + timedelta(days=4),
        )

    assert item.history(record.strategy_id) == before
    assert item.get(record.strategy_id) is record


def test_failed_transition_input_does_not_mutate_current_record():
    item = registry()
    record = register(item).record

    with pytest.raises(ValueError, match="nonempty tuple"):
        item.transition(
            record.strategy_id,
            ChallengerStatus.CHALLENGER,
            evidence_ids=(),
            reason="MISSING_EVIDENCE",
            occurred_at=T0 + timedelta(days=2),
        )
    with pytest.raises(ChallengerTransitionError, match="backward"):
        item.transition(
            record.strategy_id,
            ChallengerStatus.CHALLENGER,
            evidence_ids=("gate-1",),
            reason="STALE_EVENT",
            occurred_at=T0,
        )

    assert item.get(record.strategy_id) is record
    assert item.history(record.strategy_id) == (record,)


def test_record_model_rejects_forged_history_transition_and_evidence():
    record = register(registry()).record
    forged_event = PromotionHistoryEntry(
        sequence=1,
        from_status=ChallengerStatus.RESEARCH,
        to_status=ChallengerStatus.PAPER_CHALLENGER,
        occurred_at=T0 + timedelta(days=2),
        reason="FORGED_SKIP",
        evidence_ids=("forged",),
        previous_event_hash=record.promotion_history[0].hash,
    )

    with pytest.raises(ValueError, match="unauthorized transition"):
        StrategyChallengerRecord(
            strategy_id=record.strategy_id,
            strategy_hash=record.strategy_hash,
            parameters=record.parameters,
            evidence_ids=record.evidence_ids + ("forged",),
            status=ChallengerStatus.PAPER_CHALLENGER,
            promotion_history=record.promotion_history + (forged_event,),
            revision=1,
            previous_record_hash=record.hash,
            registered_at=record.registered_at,
            updated_at=forged_event.occurred_at,
        )
    with pytest.raises(ValueError, match="evidence differs"):
        replace(record, evidence_ids=("untracked",))


def test_list_is_sorted_and_filterable_and_unknown_lookup_is_read_only():
    item = registry()
    register(item, strategy_id="candidate-z")
    register(item, strategy_id="candidate-a")

    assert [record.strategy_id for record in item.list()] == [
        "candidate-a",
        "candidate-z",
        "prod-v8",
    ]
    assert [record.strategy_id for record in item.list(status=ChallengerStatus.RESEARCH)] == [
        "candidate-a",
        "candidate-z",
    ]
    assert item.get("unknown") is None
    assert item.history("unknown") == ()


def test_status_model_exposes_promotion_candidate_but_no_production_alias():
    assert {status.value for status in ChallengerStatus} == {
        "PRODUCTION_REFERENCE",
        "RESEARCH",
        "CHALLENGER",
        "PAPER_CHALLENGER",
        "PROMOTION_CANDIDATE",
    }
    assert not hasattr(ChallengerStatus, "PRODUCTION")
