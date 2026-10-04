"""F105B: behavior findings require supplied plans and observations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.financial.trade_behavior import (
    BehaviorTag, TradeBehaviorEvidence, analyze_trade_behavior,
)
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def trade():
    return FinancialTradeRecord(
        "synthetic:t1", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        "CME:NQ:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("98"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "TREND", (), Decimal("20"), Decimal("0"), Decimal("0"),
    )


def test_unknown_behavior_evidence_is_not_treated_as_good_discipline():
    review = analyze_trade_behavior(trade(), TradeBehaviorEvidence())
    assert not review.findings
    assert BehaviorTag.OVERTRADING in review.unknown_checks
    assert BehaviorTag.REVENGE_PATTERN_PROXY in review.unknown_checks


def test_supplied_rule_breaches_produce_explainable_proxies():
    evidence = TradeBehaviorEvidence(
        planned_entry_start=NOW + timedelta(minutes=1),
        planned_entry_end=NOW + timedelta(minutes=2),
        session_trade_index=6, max_session_trades=5,
        prior_loss_exit_at=NOW - timedelta(minutes=1),
        minimum_cooldown=timedelta(minutes=5),
        point_value=Decimal("20"), max_risk_quote=Decimal("20"),
        original_stop=Decimal("99"), approved_strategy="setup-b",
        session_rule_violation_reference="synthetic:session-rule-1",
    )
    review = analyze_trade_behavior(trade(), evidence)
    assert {finding.tag for finding in review.findings} == set(BehaviorTag) - {BehaviorTag.LATE_ENTRY}
    assert all(finding.trade_id == "synthetic:t1" for finding in review.findings)
    assert review.analysis_only
