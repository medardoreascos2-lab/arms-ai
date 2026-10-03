"""R31H tests for strict, human-gated promotion evaluation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.research.backtest_runner import ResearchParameterSet
from backend.research.challenger_registry import (
    ChallengerStatus,
    ChallengerTransitionError,
    ProductionReferenceDefinition,
    StrategyChallengerRegistry,
)
from backend.research.promotion_gate import (
    PromotionEvidence,
    PromotionGateCriteria,
    PromotionGateError,
    PromotionGateOutcome,
    StrategyPromotionGate,
)


UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def paper_candidate():
    params = ResearchParameterSet.from_mapping({"risk_units": 2, "signal": "v1"})
    registry = StrategyChallengerRegistry(
        ProductionReferenceDefinition(
            strategy_id="prod-v8",
            strategy_hash="a" * 64,
            parameters=ResearchParameterSet.from_mapping({"risk_units": 1}),
            evidence_ids=("v8-freeze",),
            registered_at=T0,
        )
    )
    research = registry.register_research(
        strategy_id="candidate-1",
        strategy_hash="b" * 64,
        parameters=params,
        evidence_ids=("backtest-1", "dataset-1"),
        registered_at=T0 + timedelta(days=1),
        reason="RESEARCH_REGISTERED",
    ).record
    challenger = registry.transition(
        research.strategy_id,
        ChallengerStatus.CHALLENGER,
        evidence_ids=("oos-pass", "walk-forward-pass"),
        reason="VALIDATION_PASSED",
        occurred_at=T0 + timedelta(days=2),
    )
    paper = registry.transition(
        challenger.strategy_id,
        ChallengerStatus.PAPER_CHALLENGER,
        evidence_ids=("paper-period-1", "stress-pass"),
        reason="PAPER_EVIDENCE_REGISTERED",
        occurred_at=T0 + timedelta(days=3),
    )
    return registry, paper


def criteria(**changes) -> PromotionGateCriteria:
    values = dict(
        minimum_trades=100,
        minimum_oos_periods=3,
        minimum_walk_forward_consistency=Decimal("0.70"),
        maximum_drawdown=Decimal("2000"),
        minimum_profit_factor=Decimal("1.20"),
        minimum_expectancy=Decimal("10"),
        minimum_stress_survival=Decimal("0.95"),
        minimum_parameter_stability=Decimal("0.80"),
    )
    values.update(changes)
    return PromotionGateCriteria(**values)


def evidence(candidate, **changes) -> PromotionEvidence:
    values = dict(
        strategy_id=candidate.strategy_id,
        challenger_record_hash=candidate.hash,
        parameter_set_sha256=candidate.parameters.sha256,
        evidence_ids=candidate.evidence_ids,
        trade_count=150,
        oos_periods=4,
        walk_forward_consistency=Decimal("0.80"),
        max_drawdown=Decimal("1500"),
        profit_factor=Decimal("1.50"),
        expectancy=Decimal("15"),
        stress_survival=Decimal("0.98"),
        parameter_stability=Decimal("0.90"),
    )
    values.update(changes)
    return PromotionEvidence(**values)


def assert_no_authority(value) -> None:
    assert value.registry_mutation_authorized is False
    assert value.execution_authorized is False
    assert value.paper_execution_authorized is False
    assert value.live_execution_authorized is False
    assert value.production_assignment_authorized is False


def test_passing_evidence_only_recommends_promotion_candidate_for_human_review():
    registry, candidate = paper_candidate()
    before = registry.history(candidate.strategy_id)

    result = StrategyPromotionGate().evaluate(
        candidate=candidate,
        evidence=evidence(candidate),
        criteria=criteria(),
        evaluated_at=T0 + timedelta(days=4),
    )

    assert result.outcome is PromotionGateOutcome.PASSED
    assert result.recommended_status is ChallengerStatus.PROMOTION_CANDIDATE
    assert result.blocking_reasons == ()
    assert result.human_operator_approval_required is True
    assert len(result.criterion_results) == 8
    assert all(item.passed for item in result.criterion_results)
    assert len(result.evaluation_id) == 64
    assert_no_authority(result)
    assert_no_authority(StrategyPromotionGate())
    assert registry.history(candidate.strategy_id) == before
    assert registry.get(candidate.strategy_id) is candidate
    assert candidate.status is ChallengerStatus.PAPER_CHALLENGER


def test_exact_boundary_values_pass_all_configurable_criteria():
    _, candidate = paper_candidate()
    rules = criteria()
    result = StrategyPromotionGate().evaluate(
        candidate=candidate,
        evidence=evidence(
            candidate,
            trade_count=rules.minimum_trades,
            oos_periods=rules.minimum_oos_periods,
            walk_forward_consistency=rules.minimum_walk_forward_consistency,
            max_drawdown=rules.maximum_drawdown,
            profit_factor=rules.minimum_profit_factor,
            expectancy=rules.minimum_expectancy,
            stress_survival=rules.minimum_stress_survival,
            parameter_stability=rules.minimum_parameter_stability,
        ),
        criteria=rules,
        evaluated_at=T0 + timedelta(days=4),
    )

    assert result.outcome is PromotionGateOutcome.PASSED


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        ("trade_count", 99, "MINIMUM_TRADES_BELOW_MINIMUM"),
        ("oos_periods", 2, "MINIMUM_OOS_PERIODS_BELOW_MINIMUM"),
        (
            "walk_forward_consistency",
            Decimal("0.69"),
            "WALK_FORWARD_CONSISTENCY_BELOW_MINIMUM",
        ),
        ("max_drawdown", Decimal("2000.01"), "MAX_DRAWDOWN_ABOVE_MAXIMUM"),
        ("profit_factor", Decimal("1.19"), "PROFIT_FACTOR_BELOW_MINIMUM"),
        ("expectancy", Decimal("9.99"), "EXPECTANCY_BELOW_MINIMUM"),
        ("stress_survival", Decimal("0.94"), "STRESS_SURVIVAL_BELOW_MINIMUM"),
        (
            "parameter_stability",
            Decimal("0.79"),
            "PARAMETER_STABILITY_BELOW_MINIMUM",
        ),
    ),
)
def test_each_failed_criterion_blocks_candidate_without_side_effects(field, value, reason):
    registry, candidate = paper_candidate()
    result = StrategyPromotionGate().evaluate(
        candidate=candidate,
        evidence=evidence(candidate, **{field: value}),
        criteria=criteria(),
        evaluated_at=T0 + timedelta(days=4),
    )

    assert result.outcome is PromotionGateOutcome.FAILED
    assert result.recommended_status is None
    assert result.blocking_reasons == (reason,)
    assert result.human_operator_approval_required is True
    assert_no_authority(result)
    assert registry.get(candidate.strategy_id) is candidate


def test_multiple_failures_are_complete_sorted_and_deterministic():
    _, candidate = paper_candidate()
    settings = criteria()
    observed = evidence(
        candidate,
        trade_count=1,
        oos_periods=0,
        walk_forward_consistency=Decimal("0"),
        max_drawdown=Decimal("9999"),
        profit_factor=Decimal("0"),
        expectancy=Decimal("-100"),
        stress_survival=Decimal("0"),
        parameter_stability=Decimal("0"),
    )
    gate = StrategyPromotionGate()

    first = gate.evaluate(
        candidate=candidate,
        evidence=observed,
        criteria=settings,
        evaluated_at=T0 + timedelta(days=4),
    )
    second = gate.evaluate(
        candidate=candidate,
        evidence=observed,
        criteria=settings,
        evaluated_at=T0 + timedelta(days=4),
    )

    assert first == second
    assert first.evaluation_id == second.evaluation_id
    assert len(first.blocking_reasons) == 8
    assert first.blocking_reasons == tuple(sorted(first.blocking_reasons))


def test_gate_requires_paper_challenger_and_does_not_advance_registry_directly():
    registry, paper = paper_candidate()
    research = registry.history(paper.strategy_id)[0]

    with pytest.raises(PromotionGateError, match="PAPER_CHALLENGER"):
        StrategyPromotionGate().evaluate(
            candidate=research,
            evidence=evidence(
                research,
                evidence_ids=research.evidence_ids,
                challenger_record_hash=research.hash,
                parameter_set_sha256=research.parameters.sha256,
            ),
            criteria=criteria(),
            evaluated_at=T0 + timedelta(days=4),
        )
    with pytest.raises(ChallengerTransitionError, match="not allowed"):
        registry.transition(
            paper.strategy_id,
            ChallengerStatus.PROMOTION_CANDIDATE,
            evidence_ids=("gate-result",),
            reason="MISSING_OPERATOR_APPROVAL_WORKFLOW",
            occurred_at=T0 + timedelta(days=4),
        )

    assert registry.get(paper.strategy_id) is paper


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"strategy_id": "candidate-2"}, "strategy does not match"),
        ({"challenger_record_hash": "c" * 64}, "current candidate revision"),
        ({"parameter_set_sha256": "d" * 64}, "parameter set does not match"),
        ({"evidence_ids": ("unregistered-evidence",)}, "registered evidence set"),
        ({"evidence_ids": ("backtest-1",)}, "registered evidence set"),
    ),
)
def test_mismatched_or_unregistered_evidence_fails_closed(change, message):
    _, candidate = paper_candidate()

    with pytest.raises(PromotionGateError, match=message):
        StrategyPromotionGate().evaluate(
            candidate=candidate,
            evidence=evidence(candidate, **change),
            criteria=criteria(),
            evaluated_at=T0 + timedelta(days=4),
        )


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"minimum_trades": 0}, "positive integer"),
        ({"minimum_oos_periods": 0}, "positive integer"),
        ({"minimum_walk_forward_consistency": Decimal("1.01")}, "between 0 and 1"),
        ({"maximum_drawdown": Decimal("-1")}, "nonnegative"),
        ({"minimum_profit_factor": Decimal("NaN")}, "finite Decimal"),
        ({"minimum_stress_survival": Decimal("-0.01")}, "nonnegative"),
        ({"minimum_parameter_stability": Decimal("Infinity")}, "finite Decimal"),
    ),
)
def test_invalid_gate_configuration_is_rejected(change, message):
    with pytest.raises(ValueError, match=message):
        criteria(**change)


@pytest.mark.parametrize(
    ("change", "message"),
    (
        ({"trade_count": -1}, "nonnegative integer"),
        ({"oos_periods": -1}, "nonnegative integer"),
        ({"walk_forward_consistency": Decimal("1.01")}, "between 0 and 1"),
        ({"max_drawdown": Decimal("-1")}, "nonnegative"),
        ({"profit_factor": Decimal("NaN")}, "finite Decimal"),
        ({"stress_survival": Decimal("-0.01")}, "nonnegative"),
        ({"parameter_stability": Decimal("Infinity")}, "finite Decimal"),
    ),
)
def test_invalid_promotion_evidence_is_rejected(change, message):
    _, candidate = paper_candidate()
    with pytest.raises(ValueError, match=message):
        evidence(candidate, **change)


def test_hashes_bind_rules_evidence_and_evaluation_time():
    _, candidate = paper_candidate()
    gate = StrategyPromotionGate()
    rules = criteria()
    observed = evidence(candidate)
    first = gate.evaluate(
        candidate=candidate,
        evidence=observed,
        criteria=rules,
        evaluated_at=T0 + timedelta(days=4),
    )
    later = gate.evaluate(
        candidate=candidate,
        evidence=observed,
        criteria=rules,
        evaluated_at=T0 + timedelta(days=5),
    )

    assert len(rules.hash) == 64
    assert len(observed.hash) == 64
    assert first.criteria_hash == rules.hash
    assert first.evidence_hash == observed.hash
    assert first.evaluation_id != later.evaluation_id


def test_no_model_defines_or_recommends_production():
    _, candidate = paper_candidate()
    result = StrategyPromotionGate().evaluate(
        candidate=candidate,
        evidence=evidence(candidate),
        criteria=criteria(),
        evaluated_at=T0 + timedelta(days=4),
    )

    assert not hasattr(ChallengerStatus, "PRODUCTION")
    assert result.recommended_status is ChallengerStatus.PROMOTION_CANDIDATE
    assert "PRODUCTION" not in result.recommended_status.value
