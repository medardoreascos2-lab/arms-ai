from datetime import datetime

import pytest

from backend.models.candle import Candle
from backend.pipeline.backtest_execution_stage import (
    BacktestExecutionStage,
)


class TradePlanStub:
    def __init__(
        self,
        authorized=True,
        decision="BUSCAR COMPRAS",
        entry_price=100.0,
        stop_loss=98.0,
        take_profit=104.0,
        contracts=2,
    ):
        self.symbol = "TEST"
        self.timeframe = "1m"
        self.authorized = authorized
        self.decision = decision
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.contracts = contracts


def build_candle(
    *,
    open_price=100.0,
    high=101.0,
    low=99.0,
    close=100.5,
):
    return Candle(
        symbol="TEST",
        timeframe="1m",
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000,
        timestamp=datetime(2026, 1, 1, 9, 31),
    )


def test_backtest_execution_stage_executes_authorized_plan():
    context = {
        "trade_plan": TradePlanStub(),
        "backtest_candle": build_candle(
            close=100.0,
        ),
        "backtest_next_candle": build_candle(
            high=104.5,
            low=99.0,
            close=103.0,
        ),
    }

    result = BacktestExecutionStage(
        point_value=2.0,
    ).run(context)

    simulated_trade = result["simulated_trade"]

    assert simulated_trade is not None
    assert simulated_trade.result == "TAKE PROFIT"
    assert simulated_trade.exit_price == 104.0
    assert simulated_trade.pnl == 16.0


def test_backtest_execution_stage_blocks_unauthorized_plan():
    context = {
        "trade_plan": TradePlanStub(
            authorized=False,
            decision="NO_TRADE",
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            contracts=0,
        ),
        "backtest_candle": build_candle(
            close=100.0,
        ),
        "backtest_next_candle": build_candle(),
    }

    result = BacktestExecutionStage().run(context)

    assert result["simulated_trade"] is None
    assert (
        result["execution_status"]
        == "Operación no ejecutada: plan no autorizado."
    )


def test_backtest_execution_stage_preserves_context():
    context = {
        "trade_plan": TradePlanStub(),
        "backtest_candle": build_candle(
            close=100.0,
        ),
        "backtest_next_candle": build_candle(),
        "session_allowed": True,
    }

    result = BacktestExecutionStage().run(context)

    assert result["session_allowed"] is True
    assert "simulated_trade" in result
    assert "execution_status" in result


def test_backtest_execution_stage_requires_trade_plan():
    with pytest.raises(
        KeyError,
        match="trade_plan",
    ):
        BacktestExecutionStage().run({})


def test_backtest_execution_stage_requires_next_candle():
    with pytest.raises(
        KeyError,
        match="backtest_next_candle",
    ):
        BacktestExecutionStage().run(
            {
                "trade_plan": TradePlanStub(),
                "backtest_candle": build_candle(
                    close=100.0,
                ),
            }
        )
