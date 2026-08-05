
from __future__ import annotations



class ExecutionDashboardProviderV2:
    """
    Provider encargado de exponer el resultado
    de ejecución para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        execution_service,
        market_context_provider=None,
        market_data_provider=None,
        account_state_provider=None,
        risk_config_provider=None,
    ):


        if not callable(
            getattr(
                execution_service,
                "execute",
                None,
            )
        ):
            raise TypeError(
                "execution_service debe implementar execute()."
            )


        self.execution_service = (
            execution_service
        )


        self.market_context_provider = (
            market_context_provider
        )


        self.market_data_provider = (
            market_data_provider
        )


        self.account_state_provider = (
            account_state_provider
        )


        self.risk_config_provider = (
            risk_config_provider
        )



    def get_execution(
        self,
    ) -> dict | None:



        if self.market_context_provider:

            market_context = (
                self.market_context_provider()
            )

        else:

            market_context = {
                "regime": "TRENDING",
                "volatility": "LOW_VOLATILITY",
                "trend": "BULLISH",
                "structure": "BOS_CONFIRMED",
                "risk_allowed": True,
            }



        if self.market_data_provider:

            market_data = (
                self.market_data_provider()
            )

        else:

            market_data = {
                "entry": 23500,
            }



        if self.account_state_provider:

            account_state = (
                self.account_state_provider()
            )

        else:

            account_state = {
                "balance": 150000,
                "daily_loss": 0,
                "max_daily_loss": 3000,
            }



        if self.risk_config_provider:

            risk_config = (
                self.risk_config_provider()
            )

        else:

            risk_config = {
                "risk_amount": 150,
                "stop_points": 50,
                "risk_reward": 2,
            }



        return self.execution_service.execute(
            market_context=market_context,
            market_data=market_data,
            account_state=account_state,
            risk_config=risk_config,
        )
