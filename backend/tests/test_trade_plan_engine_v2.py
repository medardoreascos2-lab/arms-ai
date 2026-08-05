
from backend.backtesting.trade_plan_engine_v2 import (
    TradePlanEngineV2,
)



def test_generate_buy_trade_plan():


    engine = TradePlanEngineV2()


    result = engine.generate(

        decision={
            "decision": "EXECUTE",
            "direction": "BUY",
            "confidence": 92,
        },

        market_data={
            "entry": 23500,
        },

        risk_config={
            "stop_points": 50,
            "risk_reward": 2,
        },

    )


    assert result["status"] == (
        "READY"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["entry"] == 23500


    assert result["stop_loss"] == 23450


    assert result["take_profit"] == 23600



def test_block_trade_plan_without_execution():


    engine = TradePlanEngineV2()


    result = engine.generate(

        decision={
            "decision": "BLOCK",
        },

        market_data={
            "entry": 23500,
        },

        risk_config={
            "stop_points": 50,
            "risk_reward": 2,
        },

    )


    assert result["status"] == (
        "BLOCKED"
    )
