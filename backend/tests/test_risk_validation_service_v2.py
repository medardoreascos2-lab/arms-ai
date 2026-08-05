
from backend.backtesting.risk_validation_engine_v2 import (
    RiskValidationEngineV2,
)

from backend.backtesting.risk_validation_service_v2 import (
    RiskValidationServiceV2,
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



def test_risk_validation_service_approves_trade():


    service = RiskValidationServiceV2(

        trade_plan_service=(
            FakeTradePlanService()
        ),

        risk_engine=(
            RiskValidationEngineV2()
        ),

    )


    result = service.validate(

        market_context={},

        market_data={
            "entry": 23500,
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



def test_risk_validation_service_blocks_risk_failure():


    service = RiskValidationServiceV2(

        trade_plan_service=(
            FakeTradePlanService()
        ),

        risk_engine=(
            RiskValidationEngineV2()
        ),

    )


    result = service.validate(

        market_context={},

        market_data={
            "entry": 23500,
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
