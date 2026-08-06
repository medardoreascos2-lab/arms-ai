
from backend.backtesting.risk_validation_engine_v2 import (
    RiskValidationEngineV2,
)



def test_risk_validation_accepts_valid_trade_plan():


    engine = RiskValidationEngineV2()


    result = engine.validate(

        trade_plan={

            "status": "READY",

            "direction": "BUY",

            "entry": 23500,

            "stop_loss": 23450,

            "take_profit": 23600,

        },

        risk_config={

            "max_risk": 100,

        },

    )


    assert (

        result["status"]

        ==

        "APPROVED"

    )


    assert (

        result["risk_allowed"]

        is

        True

    )



def test_risk_validation_blocks_invalid_trade_plan():


    engine = RiskValidationEngineV2()


    result = engine.validate(

        trade_plan={

            "status": "BLOCKED",

        },

        risk_config={

            "max_risk": 100,

        },

    )


    assert (

        result["status"]

        ==

        "BLOCKED"

    )


    assert (

        result["reason"]

        ==

        "INVALID_TRADE_PLAN"

    )
