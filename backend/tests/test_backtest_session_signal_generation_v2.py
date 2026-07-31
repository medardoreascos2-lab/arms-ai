import pytest

from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)
from backend.backtesting.backtest_trade_plan_adapter_v2 import (
    BacktestTradePlanAdapterV2,
)
from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
)
from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeBacktestRunner:

    def __init__(
        self,
        *,
        candle=None,
    ):
        self.candle = (
            candle
            if candle is not None
            else {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20000.0,
            }
        )

    def run(
        self,
        *,
        on_candle=None,
    ) -> int:

        if on_candle is not None:
            on_candle(
                self.candle,
                {
                    "processed": True,
                },
            )

        return 1


class FakeStrategyRunner:

    def __init__(
        self,
        *,
        action=TradingActionV2.BUY,
        metadata=None,
    ):
        self.action = action
        self.metadata = (
            metadata
            if metadata is not None
            else {
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
                "contracts": 2,
                "confluence_score": 0.90,
                "grade": "A+",
            }
        )

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        return TradingDecisionV2(
            action=self.action,
            confidence=0.92,
            reason="BACKTEST SIGNAL TEST",
            metadata=self.metadata,
        )


def build_signal_generator() -> SignalGeneratorV2:
    return SignalGeneratorV2(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
        allowed_grades={
            "A+",
            "A",
        },
    )


def build_session(
    *,
    action=TradingActionV2.BUY,
    candle=None,
    metadata=None,
    adapter=None,
    signal_generator=None,
) -> BacktestSessionV2:

    return BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(
            candle=candle,
        ),
        strategy_runner_v2=FakeStrategyRunner(
            action=action,
            metadata=metadata,
        ),
        backtest_trade_plan_adapter_v2=adapter,
        signal_generator_v2=signal_generator,
    )


def test_generates_long_signal():

    session = build_session(
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    processed = session.run()

    assert processed == 1
    assert len(session.decisions) == 1
    assert len(session.trade_plans) == 1
    assert len(session.signals) == 1

    signal = session.signals[0]

    assert signal["approved"] is True
    assert signal["status"] == "READY"
    assert signal["decision"] == "SEND_SIGNAL"
    assert signal["symbol"] == "NQ"
    assert signal["timeframe"] == "5M"
    assert signal["direction"] == "LONG"
    assert signal["entry_price"] == 20000.0
    assert signal["stop_loss"] == 19950.0
    assert signal["take_profit"] == 20100.0
    assert signal["contracts"] == 2


def test_generates_short_signal():

    session = build_session(
        action=TradingActionV2.SELL,
        metadata={
            "stop_loss": 20050.0,
            "take_profit": 19900.0,
            "contracts": 1,
            "confluence_score": 0.88,
            "grade": "A",
        },
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    session.run()

    assert len(session.signals) == 1
    assert session.signals[0]["direction"] == "SHORT"
    assert session.signals[0]["approved"] is True


def test_hold_does_not_generate_trade_plan_or_signal():

    session = build_session(
        action=TradingActionV2.HOLD,
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    processed = session.run()

    assert processed == 1
    assert len(session.decisions) == 1
    assert session.trade_plans == []
    assert session.signals == []


def test_works_without_signal_pipeline():

    session = build_session()

    processed = session.run()

    assert processed == 1
    assert len(session.decisions) == 1
    assert session.trade_plans == []
    assert session.signals == []


def test_rejects_adapter_without_build_trade_plan():

    with pytest.raises(
        TypeError,
        match="build_trade_plan",
    ):
        build_session(
            adapter=object(),
            signal_generator=build_signal_generator(),
        )


def test_rejects_generator_without_generate():

    with pytest.raises(
        TypeError,
        match="generate",
    ):
        build_session(
            adapter=BacktestTradePlanAdapterV2(),
            signal_generator=object(),
        )


def test_requires_adapter_and_generator_together():

    with pytest.raises(
        ValueError,
        match="juntos",
    ):
        build_session(
            adapter=BacktestTradePlanAdapterV2(),
            signal_generator=None,
        )


def test_requires_symbol_for_signal_generation():

    session = build_session(
        candle={
            "timeframe": "5m",
            "close": 20000.0,
        },
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        session.run()


def test_requires_timeframe_for_signal_generation():

    session = build_session(
        candle={
            "symbol": "NQ",
            "close": 20000.0,
        },
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    with pytest.raises(
        ValueError,
        match="timeframe",
    ):
        session.run()


def test_clears_signals_between_runs():

    session = build_session(
        adapter=BacktestTradePlanAdapterV2(),
        signal_generator=build_signal_generator(),
    )

    session.run()
    session.run()

    assert len(session.decisions) == 1
    assert len(session.trade_plans) == 1
    assert len(session.signals) == 1
