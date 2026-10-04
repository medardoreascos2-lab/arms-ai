"""F105C: coach summaries separate origin and instrument, preserve sample size."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.trade_behavior import BehaviorReview, BehaviorTag
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide
from backend.financial.trading_coach import summarize_trades

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def trade(record_id, strategy, pnl, asset="CME:NQ:2026-12", origin=TradeOrigin.PAPER_OBSERVED):
    return FinancialTradeRecord(
        record_id, "synthetic:journal", origin, asset, TradeSide.LONG,
        Decimal("100"), Decimal("101"), Decimal("1"), Decimal("99"), Decimal("102"),
        NOW, NOW + timedelta(minutes=1), strategy, "TREND", (), pnl,
        Decimal("0"), Decimal("0"),
    )


def test_coach_uses_observed_results_and_keeps_unknown_risk_discipline():
    trades = (trade("a", "setup-a", Decimal("10")), trade("b", "setup-b", Decimal("-5")))
    reviews = (BehaviorReview((), (BehaviorTag.RISK_INCONSISTENCY,)),
               BehaviorReview((), (BehaviorTag.RISK_INCONSISTENCY,)))
    summary = summarize_trades(trades, reviews)
    assert summary.best_setup == "setup-a"
    assert summary.what_failed == "setup-b"
    assert summary.sample_size == 2
    assert summary.risk_discipline == "UNKNOWN"
    assert summary.analysis_only


def test_coach_rejects_nq_mnq_and_actual_paper_mixing():
    review = BehaviorReview((), ())
    with pytest.raises(ValueError, match="separate"):
        summarize_trades((trade("a", "x", Decimal("1")),
                          trade("b", "x", Decimal("1"), asset="CME:MNQ:2026-12")),
                         (review, review))
    with pytest.raises(ValueError, match="separate"):
        summarize_trades((trade("a", "x", Decimal("1")),
                          trade("b", "x", Decimal("1"), origin=TradeOrigin.ACTUAL_OBSERVED)),
                         (review, review))
