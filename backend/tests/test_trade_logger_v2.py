
from backend.execution.trade_logger_v2 import (
    TradeLoggerV2,
)



def test_trade_logger_records_execution():


    logger = TradeLoggerV2()


    result = logger.log(

        execution_result={
            "status": "EXECUTED",
            "direction": "BUY",
            "entry": 23500,
            "stop_loss": 23450,
            "take_profit": 23600,
        },

        strategy_context={
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
        },

        risk_validation={
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "RECORDED"
    )


    assert result["trade"]["direction"] == (
        "BUY"
    )


    assert result["trade"]["risk_amount"] == 150



def test_trade_logger_blocks_invalid_execution():


    logger = TradeLoggerV2()


    result = logger.log(

        execution_result={
            "status": "BLOCKED",
        },

        strategy_context={},

        risk_validation={},

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_EXECUTION"
    )
