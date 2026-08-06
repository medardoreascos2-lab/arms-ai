
from backend.backtesting.execution_engine_v2 import (
    ExecutionEngineV2,
)



def test_execution_engine_accepts_approved_risk():


    engine = ExecutionEngineV2()


    result = engine.execute(

        risk_validation={

            "status": "APPROVED",

            "risk_allowed": True,

            "direction": "BUY",

        },

        trade_plan={

            "entry": 23500,

            "stop_loss": 23450,

            "take_profit": 23600,

        },

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



def test_execution_engine_blocks_invalid_risk():


    engine = ExecutionEngineV2()


    result = engine.execute(

        risk_validation={

            "status": "BLOCKED",

        },

        trade_plan={},

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
