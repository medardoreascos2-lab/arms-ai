"""F107D: premium analytics feed the coach without NQ/MNQ mixing."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.futures_coach import build_futures_coach_report
from backend.financial.futures_session import FuturesRoot, FuturesTradeContext, SessionSegment, SessionType, VolatilityLabel
from backend.financial.trade_behavior import BehaviorReview, BehaviorTag
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def context(root, trade_id):
    trade = FinancialTradeRecord(
        trade_id, "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        f"CME:{root.value}:2026-12", TradeSide.LONG, Decimal("100"), Decimal("99"),
        Decimal("1"), Decimal("98"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "RANGE", (), Decimal("-2"), Decimal("0"), Decimal("0"),
    )
    return FuturesTradeContext(trade, root, SessionType.RTH, SessionSegment.OPEN,
                               False, VolatilityLabel.NORMAL, "synthetic:classification",
                               "synthetic:dataset", "USD", ("BOS",))


def test_futures_coach_receives_setup_and_regime_evidence():
    report = build_futures_coach_report(
        (context(FuturesRoot.NQ, "synthetic:t1"),),
        (BehaviorReview((), (BehaviorTag.RISK_INCONSISTENCY,)),),
    )
    assert report.coach.asset_id == "CME:NQ:2026-12"
    assert report.setups.groups
    assert report.regimes.groups
    assert "BOS" in report.priority_note
    assert report.analysis_only


def test_futures_coach_refuses_nq_mnq_cohort():
    review = BehaviorReview((), ())
    with pytest.raises(ValueError, match="separate"):
        build_futures_coach_report((context(FuturesRoot.NQ, "a"),
                                    context(FuturesRoot.MNQ, "b")), (review, review))
