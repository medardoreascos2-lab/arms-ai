import pytest

from backend.backtesting.backtest_trade_plan_adapter_v2 import (
    BacktestTradePlanAdapterV2,
)
from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


def build_adapter() -> BacktestTradePlanAdapterV2:
    return BacktestTradePlanAdapterV2()


def build_decision(
    *,
    action=TradingActionV2.BUY,
    confidence=0.92,
    metadata=None,
) -> TradingDecisionV2:
    return TradingDecisionV2(
        action=action,
        confidence=confidence,
        reason="BACKTEST TEST DECISION",
        metadata=(
            metadata
            if metadata is not None
            else {
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
                "contracts": 2,
                "confluence_score": 0.90,
                "grade": "A+",
            }
        ),
    )


def build_candle() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "close": 20000.0,
    }


def test_builds_long_trade_plan():

    adapter = build_adapter()

    result = adapter.build_trade_plan(
        decision=build_decision(),
        candle=build_candle(),
    )

    assert result.authorized is True
    assert result.authorized is True
    assert result.decision == "EXECUTE_LONG"
    assert result.entry_price == 20000.0
    assert result.stop_loss == 19950.0
    assert result.take_profit == 20100.0
    assert result.contracts == 2
    assert result.probability == 0.92
    assert result.confluence_score == 0.90
    assert result.grade == "A+"
    assert result.decision == "EXECUTE_LONG"


def test_builds_short_trade_plan():

    adapter = build_adapter()

    decision = build_decision(
        action=TradingActionV2.SELL,
        metadata={
            "stop_loss": 20050.0,
            "take_profit": 19900.0,
            "contracts": 1,
            "confluence_score": 0.88,
            "grade": "A",
        },
    )

    result = adapter.build_trade_plan(
        decision=decision,
        candle=build_candle(),
    )

    assert result.decision == "EXECUTE_SHORT"
    assert result.decision == "EXECUTE_SHORT"
    assert result.stop_loss == 20050.0
    assert result.take_profit == 19900.0


def test_calculates_risk_reward_values():

    adapter = build_adapter()

    result = adapter.build_trade_plan(
        decision=build_decision(),
        candle=build_candle(),
    )

    risk_points = abs(
        result.entry_price - result.stop_loss
    )
    reward_points = abs(
        result.take_profit - result.entry_price
    )
    reward_risk_ratio = (
        reward_points / risk_points
    )

    assert risk_points == 50.0
    assert reward_points == 100.0
    assert reward_risk_ratio == 2.0


def test_rejects_hold_decision():

    adapter = build_adapter()

    with pytest.raises(
        ValueError,
        match="HOLD",
    ):
        adapter.build_trade_plan(
            decision=build_decision(
                action=TradingActionV2.HOLD,
            ),
            candle=build_candle(),
        )


def test_rejects_invalid_decision():

    adapter = build_adapter()

    with pytest.raises(
        TypeError,
        match="decision",
    ):
        adapter.build_trade_plan(
            decision=object(),
            candle=build_candle(),
        )


def test_rejects_invalid_candle():

    adapter = build_adapter()

    with pytest.raises(
        TypeError,
        match="candle",
    ):
        adapter.build_trade_plan(
            decision=build_decision(),
            candle=object(),
        )


def test_requires_positive_close():

    adapter = build_adapter()

    candle = build_candle()
    candle["close"] = 0.0

    with pytest.raises(
        ValueError,
        match="close",
    ):
        adapter.build_trade_plan(
            decision=build_decision(),
            candle=candle,
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "stop_loss",
        "take_profit",
        "contracts",
        "confluence_score",
        "grade",
    ],
)
def test_requires_trade_metadata_fields(
    missing_field,
):

    adapter = build_adapter()

    metadata = {
        "stop_loss": 19950.0,
        "take_profit": 20100.0,
        "contracts": 2,
        "confluence_score": 0.90,
        "grade": "A+",
    }

    metadata.pop(missing_field)

    with pytest.raises(
        ValueError,
        match=missing_field,
    ):
        adapter.build_trade_plan(
            decision=build_decision(
                metadata=metadata,
            ),
            candle=build_candle(),
        )


def test_rejects_invalid_long_levels():

    adapter = build_adapter()

    decision = build_decision(
        metadata={
            "stop_loss": 20050.0,
            "take_profit": 20100.0,
            "contracts": 2,
            "confluence_score": 0.90,
            "grade": "A+",
        },
    )

    with pytest.raises(
        ValueError,
        match="LONG",
    ):
        adapter.build_trade_plan(
            decision=decision,
            candle=build_candle(),
        )


def test_rejects_invalid_short_levels():

    adapter = build_adapter()

    decision = build_decision(
        action=TradingActionV2.SELL,
        metadata={
            "stop_loss": 19950.0,
            "take_profit": 19900.0,
            "contracts": 2,
            "confluence_score": 0.90,
            "grade": "A+",
        },
    )

    with pytest.raises(
        ValueError,
        match="SHORT",
    ):
        adapter.build_trade_plan(
            decision=decision,
            candle=build_candle(),
        )
