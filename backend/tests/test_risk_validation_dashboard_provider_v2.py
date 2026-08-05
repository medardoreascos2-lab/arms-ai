
from backend.backtesting.risk_validation_dashboard_provider_v2 import (
    RiskValidationDashboardProviderV2,
)



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
            "direction": "BUY",
        }



def test_dashboard_provider_exposes_risk_validation():


    provider = RiskValidationDashboardProviderV2(
        risk_service=(
            FakeRiskService()
        ),
    )


    result = provider.get_risk_validation()


    assert result["status"] == (
        "APPROVED"
    )


    assert result["risk_amount"] == 150



def test_dashboard_provider_without_risk_result():


    class EmptyRiskService:


        def validate(
            self,
            *,
            market_context,
            market_data,
            account_state,
            risk_config,
        ):
            return None



    provider = RiskValidationDashboardProviderV2(
        risk_service=(
            EmptyRiskService()
        ),
    )


    result = provider.get_risk_validation()


    assert result is None
