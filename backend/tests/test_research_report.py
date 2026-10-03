"""R31J tests for structured production/challenger research reports."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.backtest_runner import ResearchParameterSet
from backend.research.challenger_registry import (
    ChallengerStatus,
    ProductionReferenceDefinition,
    StrategyChallengerRegistry,
)
from backend.research.research_report import (
    AutomatedResearchReportBuilder,
    ResearchBreakdownRow,
    ResearchPerformanceMetrics,
    ResearchReportError,
    StrategyReportSource,
    StrategyResearchEvidence,
)


UTC = timezone.utc
NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def records():
    registry = StrategyChallengerRegistry(
        ProductionReferenceDefinition(
            strategy_id="prod-v8",
            strategy_hash="a" * 64,
            parameters=ResearchParameterSet.from_mapping({"risk": 1}),
            evidence_ids=("v8-freeze",),
            registered_at=NOW - timedelta(days=10),
        )
    )
    first = registry.register_research(
        strategy_id="candidate-b",
        strategy_hash="b" * 64,
        parameters=ResearchParameterSet.from_mapping({"risk": 2}),
        evidence_ids=("dataset-b", "run-b"),
        registered_at=NOW - timedelta(days=2),
        reason="RESEARCH",
    ).record
    second = registry.register_research(
        strategy_id="candidate-a",
        strategy_hash="c" * 64,
        parameters=ResearchParameterSet.from_mapping({"risk": 3}),
        evidence_ids=("dataset-a", "run-a"),
        registered_at=NOW - timedelta(days=1),
        reason="RESEARCH",
    ).record
    second = registry.transition(
        second.strategy_id,
        ChallengerStatus.CHALLENGER,
        evidence_ids=("oos-a",),
        reason="OOS_PASSED",
        occurred_at=NOW,
    )
    return registry.production_reference(), first, second


def metrics(**changes):
    values = dict(
        trade_count=100,
        win_rate=Decimal("0.60"),
        expectancy=Decimal("12.50"),
        profit_factor=Decimal("1.50"),
        max_drawdown=Decimal("900"),
        average_r=Decimal("0.35"),
        mae=Decimal("120"),
        mfe=Decimal("240"),
    )
    values.update(changes)
    return ResearchPerformanceMetrics(**values)


def rows(first="NEW_YORK", second="LONDON"):
    return tuple(sorted((
        ResearchBreakdownRow(first, 60, Decimal("0.65"), Decimal("15"), Decimal("900")),
        ResearchBreakdownRow(second, 40, Decimal("0.525"), Decimal("8.75"), Decimal("350")),
    ), key=lambda item: item.name))


def evidence(record, **changes):
    values = dict(
        strategy_id=record.strategy_id,
        challenger_record_hash=record.hash,
        evidence_ids=record.evidence_ids,
        metrics=metrics(),
        session_breakdown=rows(),
        regime_breakdown=rows("TREND", "RANGE"),
        gate_reason_breakdown=(("LOW_CONFLUENCE", 4), ("SPREAD_TOO_WIDE", 2)),
    )
    values.update(changes)
    return StrategyResearchEvidence(**values)


def source(record, **changes):
    return StrategyReportSource(record, evidence(record, **changes))


def test_report_contains_all_required_metrics_and_breakdowns_side_by_side():
    production, first, second = records()

    report = AutomatedResearchReportBuilder().build(
        production_reference=source(production),
        challengers=(source(first), source(second)),
        generated_at=NOW,
    )
    document = report.document()

    assert report.production_reference.strategy_id == "prod-v8"
    assert [item.strategy_id for item in report.challengers] == [
        "candidate-a", "candidate-b"
    ]
    assert set(document["production_reference"]["metrics"]) == {
        "average_r", "expectancy", "mae", "max_drawdown", "mfe",
        "profit_factor", "trade_count", "win_rate",
    }
    assert len(document["production_reference"]["session_breakdown"]) == 2
    assert len(document["production_reference"]["regime_breakdown"]) == 2
    assert document["production_reference"]["evidence_ids"] == ["v8-freeze"]
    assert document["production_reference"]["gate_reason_breakdown"] == [
        {"count": 4, "reason": "LOW_CONFLUENCE"},
        {"count": 2, "reason": "SPREAD_TOO_WIDE"},
    ]
    assert len(report.report_id) == 64


def test_report_never_selects_or_recommends_a_production_winner():
    production, first, _ = records()
    builder = AutomatedResearchReportBuilder()
    report = builder.build(
        production_reference=source(production),
        challengers=(source(first),),
        generated_at=NOW,
    )

    assert builder.automatic_winner_selected is False
    assert builder.execution_authorized is False
    assert builder.production_mutation_authorized is False
    assert report.automatic_winner_selected is False
    assert report.production_recommendation is None
    assert report.human_operator_review_required is True
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False


def test_challengers_are_sorted_by_identity_without_ranking_or_scoring():
    production, first, second = records()
    report = AutomatedResearchReportBuilder().build(
        production_reference=source(production),
        challengers=(source(first), source(second)),
        generated_at=NOW,
    )

    assert [item.strategy_id for item in report.challengers] == sorted(
        (first.strategy_id, second.strategy_id)
    )
    assert all(not hasattr(item, "rank") for item in report.challengers)
    assert all(not hasattr(item, "score") for item in report.challengers)


def test_mae_and_mfe_are_explicitly_optional():
    production, first, _ = records()
    challenger_source = source(first, metrics=metrics(mae=None, mfe=None))
    report = AutomatedResearchReportBuilder().build(
        production_reference=source(production),
        challengers=(challenger_source,),
        generated_at=NOW,
    )

    assert report.challengers[0].metrics.mae is None
    assert report.challengers[0].metrics.mfe is None
    assert report.document()["challengers"][0]["metrics"]["mae"] is None


def test_same_evidence_and_time_produces_same_report_identity():
    production, first, _ = records()
    production_source = source(production)
    challenger_source = source(first)
    builder = AutomatedResearchReportBuilder()

    first_report = builder.build(
        production_reference=production_source,
        challengers=(challenger_source,),
        generated_at=NOW,
    )
    second_report = builder.build(
        production_reference=production_source,
        challengers=(challenger_source,),
        generated_at=NOW,
    )
    later_report = builder.build(
        production_reference=production_source,
        challengers=(challenger_source,),
        generated_at=NOW + timedelta(seconds=1),
    )

    assert first_report == second_report
    assert first_report.report_id == second_report.report_id
    assert first_report.report_id != later_report.report_id


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"strategy_id": "other"}, "strategy does not match"),
        ({"challenger_record_hash": "f" * 64}, "current registry revision"),
        ({"evidence_ids": ("omitted",)}, "evidence IDs do not match"),
    ),
)
def test_source_binding_mismatches_fail_closed(changes, message):
    _, first, _ = records()
    with pytest.raises(ResearchReportError, match=message):
        StrategyReportSource(first, evidence(first, **changes))


def test_production_slot_requires_production_reference_status():
    _, first, second = records()
    with pytest.raises(ResearchReportError, match="PRODUCTION_REFERENCE"):
        AutomatedResearchReportBuilder().build(
            production_reference=source(first),
            challengers=(source(second),),
            generated_at=NOW,
        )


def test_challenger_list_cannot_contain_production_reference():
    production, first, _ = records()
    with pytest.raises(ResearchReportError, match="cannot contain"):
        AutomatedResearchReportBuilder().build(
            production_reference=source(production),
            challengers=(source(first), source(production)),
            generated_at=NOW,
        )


def test_duplicate_challenger_identity_is_rejected():
    production, first, _ = records()
    first_source = source(first)
    with pytest.raises(ResearchReportError, match="unique"):
        AutomatedResearchReportBuilder().build(
            production_reference=source(production),
            challengers=(first_source, first_source),
            generated_at=NOW,
        )


def test_session_and_regime_trade_counts_must_reconcile_to_total():
    _, first, _ = records()
    incomplete = (
        ResearchBreakdownRow("NEW_YORK", 99, Decimal("0.5"), Decimal("1"), Decimal("1")),
    )

    with pytest.raises(ValueError, match="session_breakdown trade count"):
        evidence(first, session_breakdown=incomplete)
    with pytest.raises(ValueError, match="regime_breakdown trade count"):
        evidence(first, regime_breakdown=incomplete)


def test_breakdowns_and_gate_reasons_require_sorted_unique_names():
    _, first, _ = records()
    unsorted_rows = tuple(reversed(rows()))
    with pytest.raises(ValueError, match="sorted with unique"):
        evidence(first, session_breakdown=unsorted_rows)
    with pytest.raises(ValueError, match="sorted with unique"):
        evidence(first, gate_reason_breakdown=(("Z_REASON", 1), ("A_REASON", 2)))
    with pytest.raises(ValueError, match="sorted with unique"):
        evidence(first, gate_reason_breakdown=(("SAME", 1), ("SAME", 2)))


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"trade_count": 0}, ">= 1"),
        ({"win_rate": Decimal("1.01")}, "between 0 and 1"),
        ({"profit_factor": Decimal("-1")}, "nonnegative"),
        ({"max_drawdown": Decimal("-1")}, "nonnegative"),
        ({"expectancy": Decimal("NaN")}, "finite Decimal"),
        ({"average_r": Decimal("Infinity")}, "finite Decimal"),
        ({"mae": Decimal("-1")}, "nonnegative"),
        ({"mfe": Decimal("NaN")}, "finite Decimal"),
    ),
)
def test_invalid_report_metrics_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        metrics(**changes)


def test_report_module_has_no_execution_or_automatic_promotion_integration():
    import backend.research.research_report as module

    source_text = Path(module.__file__).read_text(encoding="utf-8")
    assert "EnterLong" not in source_text
    assert "EnterShort" not in source_text
    assert "submit_order" not in source_text
    assert "automatic_winner_selected = True" not in source_text
    assert "production_mutation_authorized = True" not in source_text
