
from backend.execution.execution_engine_v2 import (
    ExecutionEngineV2,
)

from backend.execution.execution_service_v2 import (
    ExecutionServiceV2,
)



class FakeTradePlanService:


    def generate(
        self,
        *,
        market_context,
        market_data,
        risk_config,
    ):

        return {
            "status": "READY",
            "direction": "BUY",
            "entry": 23500,
            "stop_loss": 23450,
            "take_profit": 23600,
        }



class FakeRiskService:


    def validate(
        self,
        *,
        market_context,
        market_data,
        account_state,
        risk_config,
    ):

        return {
            "status": "APPROVED",
            "risk_amount": 150,
        }



def test_execution_service_executes_trade():


    service = ExecutionServiceV2(

        trade_plan_service=(
            FakeTradePlanService()
        ),

        risk_service=(
            FakeRiskService()
        ),

        execution_engine=(
            ExecutionEngineV2()
        ),

    )


    result = service.execute(

        market_context={},

        market_data={
            "entry": 23500,
        },

        account_state={
            "balance": 150000,
        },

        risk_config={
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "EXECUTED"
    )


    assert result["direction"] == (
        "BUY"
    )



def test_execution_service_blocks_risk_failure():


    class BlockRiskService:


        def validate(
            self,
            *,
            market_context,
            market_data,
            account_state,
            risk_config,
        ):

            return {
                "status": "BLOCKED",
            }



    service = ExecutionServiceV2(

        trade_plan_service=(
            FakeTradePlanService()
        ),

        risk_service=(
            BlockRiskService()
        ),

        execution_engine=(
            ExecutionEngineV2()
        ),

    )


    result = service.execute(

        market_context={},

        market_data={},

        account_state={},

        risk_config={},

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "RISK_NOT_APPROVED"
    )
