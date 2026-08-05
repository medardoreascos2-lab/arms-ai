
from backend.backtesting.trade_plan_dashboard_provider_v2 import (
    TradePlanDashboardProviderV2,
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



def test_dashboard_provider_exposes_trade_plan():


    provider = TradePlanDashboardProviderV2(
        trade_plan_service=(
            FakeTradePlanService()
        ),
    )


    result = provider.get_trade_plan()


    assert result["status"] == (
        "READY"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["entry"] == 23500



def test_dashboard_provider_without_plan():


    class EmptyService:


        def generate(
            self,
            *,
            market_context,
            market_data,
            risk_config,
        ):
            return None



    provider = TradePlanDashboardProviderV2(
        trade_plan_service=(
            EmptyService()
        ),
    )


    result = provider.get_trade_plan()


    assert result is None
