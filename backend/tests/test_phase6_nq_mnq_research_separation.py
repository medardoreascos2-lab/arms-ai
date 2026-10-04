"""R73C tests preventing silent NQ/MNQ research aggregation."""

from decimal import Decimal

import pytest

from backend.phase6.research_separation import (
    InstrumentResearchResult,
    ResearchRunIdentity,
    ResearchSeparationError,
    build_instrument_report,
    build_labeled_aggregate,
)


def _result(instrument: str, run: str, metric: str = "net_r"):
    return InstrumentResearchResult(
        identity=ResearchRunIdentity(
            run_id=run,
            instrument=instrument,
            contract_id=f"{instrument}-2031-03",
            dataset_id=f"synthetic-{instrument.lower()}-normal-v1",
        ),
        metrics={metric: Decimal("1.25")},
    )


def test_nq_and_mnq_runs_have_distinct_storage_and_reports():
    nq_result = _result("NQ", "run-1")
    mnq_result = _result("MNQ", "run-1")
    nq_report = build_instrument_report("NQ", (nq_result,))
    mnq_report = build_instrument_report("MNQ", (mnq_result,))

    assert nq_result.identity.storage_key.startswith("research/NQ/")
    assert mnq_result.identity.storage_key.startswith("research/MNQ/")
    assert nq_result.identity.storage_key != mnq_result.identity.storage_key
    assert nq_report.label == "NQ_ONLY"
    assert mnq_report.label == "MNQ_ONLY"
    assert nq_report.instrument != mnq_report.instrument


def test_mixed_result_in_single_instrument_report_is_rejected():
    with pytest.raises(ResearchSeparationError, match="mixed"):
        build_instrument_report("NQ", (_result("NQ", "nq"), _result("MNQ", "mnq")))


def test_aggregate_requires_exact_explicit_label_and_methodology():
    nq = build_instrument_report("NQ", (_result("NQ", "nq"),))
    mnq = build_instrument_report("MNQ", (_result("MNQ", "mnq"),))

    with pytest.raises(ResearchSeparationError, match="label"):
        build_labeled_aggregate((nq, mnq), label="combined", methodology="side by side")
    with pytest.raises(ResearchSeparationError, match="methodology"):
        build_labeled_aggregate((nq, mnq), label="AGGREGATED[MNQ+NQ]", methodology="")

    aggregate = build_labeled_aggregate(
        (nq, mnq),
        label="AGGREGATED[MNQ+NQ]",
        methodology="side-by-side instrument sections; no combined metric",
    )
    assert aggregate.instruments == ("MNQ", "NQ")
    assert aggregate.combined_performance is None
    assert aggregate.execution_authorized is False


def test_duplicate_instrument_or_single_report_cannot_claim_aggregation():
    nq = build_instrument_report("NQ", (_result("NQ", "nq"),))

    with pytest.raises(ResearchSeparationError, match="multiple"):
        build_labeled_aggregate((nq,), label="AGGREGATED[NQ]", methodology="invalid")
    with pytest.raises(ResearchSeparationError, match="repeat"):
        build_labeled_aggregate((nq, nq), label="AGGREGATED[NQ+NQ]", methodology="invalid")


def test_contract_instrument_mismatch_and_non_decimal_metrics_fail_closed():
    with pytest.raises(ResearchSeparationError, match="does not match"):
        ResearchRunIdentity("run", "NQ", "MNQ-2031-03", "synthetic")
    with pytest.raises(ResearchSeparationError, match="Decimal"):
        InstrumentResearchResult(
            identity=ResearchRunIdentity("run", "NQ", "NQ-2031-03", "synthetic"),
            metrics={"net_r": 1.25},
        )


def test_research_result_rejects_real_data_claim_and_execution_authority():
    identity = ResearchRunIdentity("run", "MNQ", "MNQ-2031-03", "synthetic")
    with pytest.raises(ResearchSeparationError, match="synthetic"):
        InstrumentResearchResult(identity, {"net_r": Decimal("1")}, synthetic_data=False)
    with pytest.raises(ResearchSeparationError, match="authorize execution"):
        InstrumentResearchResult(identity, {"net_r": Decimal("1")}, execution_authorized=True)
