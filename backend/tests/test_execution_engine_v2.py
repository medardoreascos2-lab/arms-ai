
from backend.execution.execution_engine_v2 import (
    ExecutionEngineV2,
)



def test_execution_engine_executes_approved_trade():


    engine = ExecutionEngineV2()


    result = engine.execute(

        trade_plan={
            "status": "READY",
            "direction": "BUY",
            "entry": 23500,
            "stop_loss": 23450,
            "take_profit": 23600,
        },

        risk_validation={
            "status": "APPROVED",
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "EXECUTED"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["entry"] == 23500



def test_execution_engine_blocks_invalid_risk():


    engine = ExecutionEngineV2()


    result = engine.execute(

        trade_plan={
            "status": "READY",
            "direction": "BUY",
            "entry": 23500,
        },

        risk_validation={
            "status": "BLOCKED",
            "reason": "DAILY_LOSS_LIMIT_REACHED",
        },

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "RISK_NOT_APPROVED"
    )



def test_execution_engine_blocks_invalid_trade_plan():


    engine = ExecutionEngineV2()


    result = engine.execute(

        trade_plan={
            "status": "BLOCKED",
        },

        risk_validation={
            "status": "APPROVED",
        },

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_TRADE_PLAN"
    )
