from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.paper_challenger_validation import (
    PaperChallengerValidationModel,
    PaperFaultEvidence,
    PaperSessionEvidence,
    PaperStrategyIdentity,
    PaperTradeEvidence,
    PaperValidationMetrics,
)


NOW = datetime(2026, 10, 3, 14, tzinfo=timezone.utc)


def identity(identifier: str, role: str) -> PaperStrategyIdentity:
    return PaperStrategyIdentity(identifier, "a" * 64, "b" * 64, 2, role)


def session(identifier: str = "session-1", candidate: str = "candidate") -> PaperSessionEvidence:
    return PaperSessionEvidence(
        session_id=identifier,
        candidate_id=candidate,
        started_at=NOW,
        ended_at=NOW + timedelta(hours=1),
        trades=(
            PaperTradeEvidence("trade-1", identifier, NOW, NOW + timedelta(minutes=10), Decimal("1")),
            PaperTradeEvidence("trade-2", identifier, NOW + timedelta(minutes=20), NOW + timedelta(minutes=30), Decimal("-2")),
        ),
        faults=(PaperFaultEvidence("fault-1", identifier, NOW + timedelta(minutes=15), "QUOTE_STALE", "quote was stale"),),
    )


def reference_metrics() -> PaperValidationMetrics:
    return PaperValidationMetrics(4, 2, Decimal("2"), Decimal(".5"), Decimal("1"))


def test_build_stores_identity_sessions_trades_faults_metrics_and_comparison() -> None:
    report = PaperChallengerValidationModel().build(
        candidate=identity("candidate", "PAPER_CHALLENGER"),
        production_reference=identity("production", "PRODUCTION_REFERENCE"),
        sessions=(session(),), reference_metrics=reference_metrics(), generated_at=NOW,
    )

    assert report.candidate.strategy_id == "candidate"
    assert len(report.sessions) == 1
    assert len(report.sessions[0].trades) == 2
    assert len(report.sessions[0].faults) == 1
    assert report.comparison.candidate.trade_count == 2
    assert report.comparison.candidate.total_net_r == Decimal("-1")
    assert report.comparison.candidate.max_drawdown_r == Decimal("2")
    assert report.comparison.average_net_r_delta == Decimal("-1")


def test_report_is_simulated_paper_only_without_live_or_broker_authority() -> None:
    report = PaperChallengerValidationModel().build(
        candidate=identity("candidate", "PAPER_CHALLENGER"), production_reference=identity("production", "PRODUCTION_REFERENCE"),
        sessions=(session(),), reference_metrics=reference_metrics(), generated_at=NOW,
    )
    assert report.execution_kind == "SIMULATED_PAPER"
    assert report.broker_execution_authorized is False
    assert report.live_execution_authorized is False
    assert report.production_mutation_authorized is False


def test_real_trade_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be simulated"):
        PaperTradeEvidence("trade", "session", NOW, NOW, Decimal("1"), simulated=False)


@pytest.mark.parametrize("candidate_role,reference_role", [
    ("PRODUCTION_REFERENCE", "PRODUCTION_REFERENCE"),
    ("PAPER_CHALLENGER", "PAPER_CHALLENGER"),
])
def test_report_enforces_separate_candidate_and_reference_roles(candidate_role: str, reference_role: str) -> None:
    with pytest.raises(ValueError, match="roles"):
        PaperChallengerValidationModel().build(
            candidate=identity("candidate", candidate_role), production_reference=identity("production", reference_role),
            sessions=(session(),), reference_metrics=reference_metrics(), generated_at=NOW,
        )


def test_session_candidate_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="candidate identity"):
        PaperChallengerValidationModel().build(
            candidate=identity("other", "PAPER_CHALLENGER"), production_reference=identity("production", "PRODUCTION_REFERENCE"),
            sessions=(session(),), reference_metrics=reference_metrics(), generated_at=NOW,
        )


def test_trade_and_fault_must_belong_to_session_and_time_window() -> None:
    bad_trade = PaperTradeEvidence("trade", "different", NOW, NOW, Decimal("0"))
    with pytest.raises(ValueError, match="identity mismatch"):
        PaperSessionEvidence("session", "candidate", NOW, NOW + timedelta(hours=1), (bad_trade,), ())
    bad_fault = PaperFaultEvidence("fault", "session", NOW + timedelta(hours=2), "FAULT", "late")
    with pytest.raises(ValueError, match="outside session"):
        PaperSessionEvidence("session", "candidate", NOW, NOW + timedelta(hours=1), (), (bad_fault,))


def test_session_evidence_is_sorted_and_unique() -> None:
    first = PaperTradeEvidence("a", "session", NOW, NOW, Decimal("0"))
    second = PaperTradeEvidence("b", "session", NOW, NOW, Decimal("0"))
    with pytest.raises(ValueError, match="must be sorted"):
        PaperSessionEvidence("session", "candidate", NOW, NOW, (second, first), ())


def test_metrics_must_reconcile() -> None:
    with pytest.raises(ValueError, match="average_net_r"):
        PaperValidationMetrics(2, 1, Decimal("2"), Decimal("2"), Decimal("0"))


def test_source_and_report_hashes_are_deterministic() -> None:
    kwargs = dict(candidate=identity("candidate", "PAPER_CHALLENGER"), production_reference=identity("production", "PRODUCTION_REFERENCE"),
                  sessions=(session(),), reference_metrics=reference_metrics(), generated_at=NOW)
    first = PaperChallengerValidationModel().build(**kwargs)
    second = PaperChallengerValidationModel().build(**kwargs)
    assert first.source_hash == second.source_hash
    assert first.report_hash == second.report_hash


def test_module_has_no_broker_submission_calls() -> None:
    text = (Path(__file__).parents[1] / "research" / "paper_challenger_validation.py").read_text(encoding="utf-8")
    assert "EnterLong" not in text
    assert "EnterShort" not in text
    assert "submit_order" not in text
    assert "broker.send" not in text
