"""F105A: observed records never imply new fills or order authority."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def trade(**changes):
    data = dict(record_id="synthetic:trade-1", source="synthetic:journal", origin=TradeOrigin.PAPER_OBSERVED,
                asset_id="CME:MNQ:2026-12", side=TradeSide.LONG,
                entry_price=Decimal("100"), exit_price=Decimal("102"), size=Decimal("1"),
                stop_price=Decimal("99"), target_price=Decimal("102"),
                entry_at=NOW, exit_at=NOW + timedelta(minutes=5),
                strategy="synthetic:setup", market_regime="TREND",
                decision_evidence=("synthetic:signal-1",), result_pnl=Decimal("4"),
                fees=Decimal("0"), slippage=Decimal("0"))
    data.update(changes)
    return FinancialTradeRecord(**data)


def test_record_preserves_instrument_and_observed_origin_without_execution():
    item = trade()
    assert item.asset_id == "CME:MNQ:2026-12"
    assert item.origin is TradeOrigin.PAPER_OBSERVED
    assert item.result_pnl == Decimal("4")
    assert not hasattr(item, "submit_order")


def test_result_cannot_exist_without_observed_exit():
    with pytest.raises(ValueError, match="result requires"):
        trade(exit_price=None)
    with pytest.raises(ValueError, match="exit timestamp"):
        trade(exit_at=None)
