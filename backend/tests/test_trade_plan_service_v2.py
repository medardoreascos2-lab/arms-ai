
from backend.backtesting.trade_plan_engine_v2 import (
    TradePlanEngineV2,
)

from backend.backtesting.trade_plan_service_v2 import (
    TradePlanServiceV2,
)



class FakeDecisionService:


    def decide(
        self,
        *,
        market_context,
    ):

        return {
            "decision": "EXECUTE",
            "direction": "BUY",
            "confidence": 92,
        }



def test_trade_plan_service_generates_plan():


    service = TradePlanServiceV2(

        decision_service=(
            FakeDecisionService()
        ),

        trade_plan_engine=(
            TradePlanEngineV2()
        ),

    )


    result = service.generate(

        market_context={
            "trend": "BULLISH",
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


    assert result["stop_loss"] == 23450



def test_trade_plan_service_blocks_decision():


    class BlockDecision:


        def decide(
            self,
            *,
            market_context,
        ):

            return {
                "decision": "BLOCK",
            }



    service = TradePlanServiceV2(

        decision_service=(
            BlockDecision()
        ),

        trade_plan_engine=(
            TradePlanEngineV2()
        ),

    )


    result = service.generate(

        market_context={},

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
