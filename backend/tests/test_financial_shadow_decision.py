"""F106A: shadow plans are tied to observed trades and never executable."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.shadow_decision import ShadowDecision, ShadowDecisionPair
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def trade():
    return FinancialTradeRecord(
        "synthetic:t1", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        "CME:NQ:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("99"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "TREND", (), Decimal("20"), Decimal("0"), Decimal("0"),
    )


def shadow(**changes):
    data = dict(trade_record_id="synthetic:t1", asset_id="CME:NQ:2026-12",
                decided_at=NOW, would_trade=True, side=TradeSide.LONG, entry=Decimal("100"),
                stop=Decimal("99"), target=Decimal("102"), reason="synthetic setup",
                confidence=Decimal("0.8"), evidence=("synthetic:signal",))
    data.update(changes)
    return ShadowDecision(**data)


def test_shadow_pair_is_hypothetical_and_nonexecuting():
    pair = ShadowDecisionPair(trade(), shadow())
    assert pair.medar_shadow_decision.label == "HYPOTHETICAL"
    assert not pair.medar_shadow_decision.execution_authority
    assert not hasattr(pair.medar_shadow_decision, "submit_order")


def test_future_decision_or_unevidenced_plan_rejected():
    with pytest.raises(ValueError, match="precede"):
        ShadowDecisionPair(trade(), shadow(decided_at=NOW + timedelta(seconds=1)))
    with pytest.raises(ValueError, match="evidence"):
        shadow(evidence=())
