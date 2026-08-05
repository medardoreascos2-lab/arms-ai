
from backend.backtesting.risk_validation_engine_v2 import (
    RiskValidationEngineV2,
)



def test_risk_validation_approves_valid_trade_plan():


    engine = RiskValidationEngineV2()


    result = engine.validate(

        trade_plan={
            "status": "READY",
            "direction": "BUY",
            "entry": 23500,
            "stop_loss": 23450,
            "take_profit": 23600,
        },

        account_state={
            "balance": 150000,
            "daily_loss": 0,
            "max_daily_loss": 3000,
        },

        risk_config={
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "APPROVED"
    )



def test_risk_validation_blocks_daily_loss_limit():


    engine = RiskValidationEngineV2()


    result = engine.validate(

        trade_plan={
            "status": "READY",
        },

        account_state={
            "balance": 150000,
            "daily_loss": 3000,
            "max_daily_loss": 3000,
        },

        risk_config={
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "DAILY_LOSS_LIMIT_REACHED"
    )



def test_risk_validation_blocks_invalid_trade_plan():


    engine = RiskValidationEngineV2()


    result = engine.validate(

        trade_plan={
            "status": "BLOCKED",
        },

        account_state={
            "daily_loss": 0,
            "max_daily_loss": 3000,
        },

        risk_config={
            "risk_amount": 150,
        },

    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_TRADE_PLAN"
    )
