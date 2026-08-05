
from backend.execution.execution_dashboard_provider_v2 import (
    ExecutionDashboardProviderV2,
)



class FakeExecutionService:


    def execute(
        self,
        *,
        market_context,
        market_data,
        account_state,
        risk_config,
    ):

        return {
            "status": "EXECUTED",
            "direction": "BUY",
            "entry": 23500,
        }



def test_dashboard_provider_exposes_execution():


    provider = ExecutionDashboardProviderV2(
        execution_service=(
            FakeExecutionService()
        ),
    )


    result = provider.get_execution()


    assert result["status"] == (
        "EXECUTED"
    )


    assert result["direction"] == (
        "BUY"
    )



def test_dashboard_provider_without_execution():


    class EmptyExecutionService:


        def execute(
            self,
            *,
            market_context,
            market_data,
            account_state,
            risk_config,
        ):
            return None



    provider = ExecutionDashboardProviderV2(
        execution_service=(
            EmptyExecutionService()
        ),
    )


    result = provider.get_execution()


    assert result is None
