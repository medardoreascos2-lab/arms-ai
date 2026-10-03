"""R31K tests for observed and hypothetical decision-trace analytics."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.decision_trace_analytics import (
    HYPOTHETICAL_LABEL,
    DecisionTraceOutcome,
    DecisionTraceRecord,
    DecisionTraceResearchAnalytics,
    TraceAction,
    TraceOutcomeKind,
)


UTC = timezone.utc
NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def trace(trace_id, action, *, accepted=False, candidate=None, reasons=(), near=False, confidence="0.5"):
    return DecisionTraceRecord(
        trace_id=trace_id,
        timestamp=NOW + timedelta(minutes=int(trace_id[-1])),
        action=action,
        accepted=accepted,
        candidate_action=candidate,
        blocking_reasons=reasons,
        near_miss=near,
        factors=(("confidence", Decimal(confidence)), ("quality", Decimal("80"))),
    )


def sample():
    traces = (
        trace("trace-1", TraceAction.HOLD, candidate=TraceAction.BUY,
              reasons=("LOW_PROBABILITY",), near=True, confidence="0.2"),
        trace("trace-2", TraceAction.HOLD, candidate=TraceAction.SELL,
              reasons=("LOW_CONFLUENCE",), near=True, confidence="0.8"),
        trace("trace-3", TraceAction.BUY, accepted=True, confidence="0.9"),
        trace("trace-4", TraceAction.SELL, candidate=TraceAction.SELL,
              reasons=("RISK_BLOCKED",), confidence="0.1"),
        trace("trace-5", TraceAction.HOLD, confidence="0.5"),
    )
    outcomes = (
        DecisionTraceOutcome("trace-1", TraceOutcomeKind.HYPOTHETICAL, Decimal("-1"), NOW + timedelta(hours=1)),
        DecisionTraceOutcome("trace-2", TraceOutcomeKind.HYPOTHETICAL, Decimal("2"), NOW + timedelta(hours=1)),
        DecisionTraceOutcome("trace-3", TraceOutcomeKind.OBSERVED, Decimal("1"), NOW + timedelta(hours=1)),
        DecisionTraceOutcome("trace-4", TraceOutcomeKind.HYPOTHETICAL, Decimal("-2"), NOW + timedelta(hours=1)),
        DecisionTraceOutcome("trace-5", TraceOutcomeKind.HYPOTHETICAL, Decimal("0"), NOW + timedelta(hours=1)),
    )
    return traces, outcomes


def analyze():
    traces, outcomes = sample()
    return DecisionTraceResearchAnalytics().analyze(
        traces=traces, outcomes=outcomes, generated_at=NOW + timedelta(hours=2)
    )


def test_classifies_hold_quality_and_profitable_counterfactuals_as_hypothetical():
    result = analyze()
    by_id = {item.trace_id: item for item in result.classifications}

    assert by_id["trace-1"].hold_remained_poor is True
    assert by_id["trace-2"].hold_became_profitable is True
    assert by_id["trace-5"].hold_remained_poor is True
    assert by_id["trace-1"].outcome_kind is TraceOutcomeKind.HYPOTHETICAL
    assert by_id["trace-1"].outcome_label == HYPOTHETICAL_LABEL
    assert result.counterfactual_results_are_hypothetical is True
    assert result.hypothetical_label == HYPOTHETICAL_LABEL


def test_identifies_gates_that_prevented_losses_and_blocked_profit():
    result = analyze()
    gates = {item.reason: item for item in result.gate_summaries}

    assert gates["LOW_PROBABILITY"].prevented_loss_count == 1
    assert gates["LOW_PROBABILITY"].blocked_profitable_count == 0
    assert gates["LOW_CONFLUENCE"].prevented_loss_count == 0
    assert gates["LOW_CONFLUENCE"].blocked_profitable_count == 1
    assert gates["RISK_BLOCKED"].prevented_loss_count == 1
    assert all(item.blocked_count == 1 for item in gates.values())


def test_counts_near_misses_candidate_entries_and_actions():
    result = analyze()
    summaries = {item.action: item for item in result.action_summaries}

    assert result.near_miss_count == 2
    assert result.profitable_near_miss_count == 1
    assert result.candidate_entry_count == 3
    assert summaries[TraceAction.HOLD].count == 3
    assert summaries[TraceAction.HOLD].total_net_r == Decimal("1")
    assert summaries[TraceAction.BUY].count == 1
    assert summaries[TraceAction.SELL].count == 1


def test_factor_associations_are_descriptive_and_not_causal():
    result = analyze()
    factors = {item.factor: item for item in result.factor_associations}

    assert factors["confidence"].sample_count == 5
    assert factors["confidence"].correlation_with_profitable_outcome > 0
    assert factors["confidence"].interpretation == "DESCRIPTIVE_ASSOCIATION_NOT_CAUSATION"
    assert factors["quality"].correlation_with_profitable_outcome is None


def test_accepted_entry_is_observed_and_never_reclassified_as_counterfactual():
    result = analyze()
    observed = next(item for item in result.classifications if item.trace_id == "trace-3")

    assert observed.outcome_kind is TraceOutcomeKind.OBSERVED
    assert observed.outcome_label == "OBSERVED_EXECUTION_OUTCOME"
    assert observed.profitable is True
    assert observed.gate_prevented_loss is False
    assert observed.gate_blocked_profitable_opportunity is False


def test_analysis_is_deterministic_and_binds_sorted_source_evidence():
    traces, outcomes = sample()
    engine = DecisionTraceResearchAnalytics()
    first = engine.analyze(traces=traces, outcomes=outcomes, generated_at=NOW)
    second = engine.analyze(
        traces=tuple(reversed(traces)),
        outcomes=tuple(reversed(outcomes)),
        generated_at=NOW,
    )

    assert first == second
    assert first.source_hash == second.source_hash
    assert first.result_hash == second.result_hash
    assert [item.trace_id for item in first.classifications] == [
        "trace-1", "trace-2", "trace-3", "trace-4", "trace-5"
    ]


def test_missing_extra_or_duplicate_outcomes_fail_closed():
    traces, outcomes = sample()
    engine = DecisionTraceResearchAnalytics()
    with pytest.raises(ValueError, match="exactly one outcome"):
        engine.analyze(traces=traces, outcomes=outcomes[:-1], generated_at=NOW)
    with pytest.raises(ValueError, match="unique"):
        engine.analyze(traces=traces, outcomes=outcomes + (outcomes[0],), generated_at=NOW)
    extra = DecisionTraceOutcome(
        "trace-extra", TraceOutcomeKind.HYPOTHETICAL, Decimal("0"), NOW
    )
    with pytest.raises(ValueError, match="exactly one outcome"):
        engine.analyze(traces=traces, outcomes=outcomes + (extra,), generated_at=NOW)


def test_unexecuted_outcome_cannot_be_presented_as_observed():
    traces, outcomes = sample()
    forged = (replace(outcomes[0], kind=TraceOutcomeKind.OBSERVED),) + outcomes[1:]
    with pytest.raises(ValueError, match="must be HYPOTHETICAL"):
        DecisionTraceResearchAnalytics().analyze(
            traces=traces, outcomes=forged, generated_at=NOW
        )


def test_executed_outcome_cannot_be_presented_as_hypothetical():
    traces, outcomes = sample()
    forged = outcomes[:2] + (
        replace(outcomes[2], kind=TraceOutcomeKind.HYPOTHETICAL),
    ) + outcomes[3:]
    with pytest.raises(ValueError, match="must be OBSERVED"):
        DecisionTraceResearchAnalytics().analyze(
            traces=traces, outcomes=forged, generated_at=NOW
        )


def test_outcome_horizon_cannot_precede_trace():
    traces, outcomes = sample()
    forged = (replace(outcomes[0], evaluated_until=NOW),) + outcomes[1:]
    with pytest.raises(ValueError, match="cannot precede"):
        DecisionTraceResearchAnalytics().analyze(
            traces=traces, outcomes=forged, generated_at=NOW
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"accepted": True}, "HOLD cannot be accepted"),
        ({"near_miss": True}, "near-miss HOLD requires"),
        ({"blocking_reasons": ("Z", "A")}, "sorted and unique"),
        ({"factors": (("z", Decimal("1")), ("a", Decimal("2")))}, "sorted with unique"),
    ),
)
def test_invalid_hold_trace_contracts_are_rejected(changes, message):
    values = dict(
        trace_id="hold-1", timestamp=NOW, action=TraceAction.HOLD,
        accepted=False, candidate_action=None, blocking_reasons=(),
        near_miss=False, factors=(("confidence", Decimal("0.5")),),
    )
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        DecisionTraceRecord(**values)


def test_rejected_entry_requires_gate_reason_and_accepted_entry_forbids_it():
    with pytest.raises(ValueError, match="requires blocking reasons"):
        trace("trace-6", TraceAction.BUY)
    with pytest.raises(ValueError, match="accepted decision cannot"):
        trace("trace-6", TraceAction.BUY, accepted=True, reasons=("RISK",))


@pytest.mark.parametrize("value", (Decimal("NaN"), Decimal("Infinity")))
def test_nonfinite_outcome_is_rejected(value):
    with pytest.raises(ValueError, match="finite Decimal"):
        DecisionTraceOutcome("trace-1", TraceOutcomeKind.HYPOTHETICAL, value, NOW)


def test_analysis_never_rewrites_strategy_or_authorizes_execution():
    engine = DecisionTraceResearchAnalytics()
    result = analyze()

    assert engine.strategy_rewrite_authorized is False
    assert engine.execution_authorized is False
    assert result.strategy_rewrite_authorized is False
    assert result.execution_authorized is False
    source = Path(__import__(
        "backend.research.decision_trace_analytics", fromlist=["x"]
    ).__file__).read_text(encoding="utf-8")
    assert "strategy_rewrite_authorized = True" not in source
    assert "execution_authorized = True" not in source
    assert "submit_order" not in source
