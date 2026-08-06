
from backend.backtesting.execution_service_v2 import (
    ExecutionServiceV2,
)

from backend.backtesting.execution_engine_v2 import (
    ExecutionEngineV2,
)



class FakeRiskService:


    def validate_trade(
        self,
        *,
        trade_plan,
    ):

        return {
            "status": "APPROVED",
            "risk_allowed": True,
            "direction": "BUY",
        }



def test_execution_service_executes_approved_trade():


    service = ExecutionServiceV2(

        risk_service=(

            FakeRiskService()

        ),

        execution_engine=(

            ExecutionEngineV2()

        ),

    )


    result = service.execute(

        trade_plan={

            "direction": "BUY",

            "entry": 23500,

            "stop_loss": 23450,

            "take_profit": 23600,

        }

    )


    assert (

        result["status"]

        ==

        "READY"

    )


    assert (

        result["action"]

        ==

        "BUY"

    )



def test_execution_service_blocks_invalid_risk():


    class EmptyRiskService:


        def validate_trade(
            self,
            *,
            trade_plan,
        ):

            return {

                "status": "BLOCKED"

            }



    service = ExecutionServiceV2(

        risk_service=(

            EmptyRiskService()

        ),

        execution_engine=(

            ExecutionEngineV2()

        ),

    )


    result = service.execute(

        trade_plan={}

    )


    assert (

        result["status"]

        ==

        "BLOCKED"

    )


    assert (

        result["reason"]

        ==

        "RISK_NOT_APPROVED"

    )
