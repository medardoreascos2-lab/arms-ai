
from __future__ import annotations



class RiskValidationDashboardProviderV2:
    """
    Provider encargado de exponer la validación
    de riesgo para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        risk_service,
        market_context_provider=None,
        market_data_provider=None,
        account_state_provider=None,
        risk_config_provider=None,
    ):


        if not callable(
            getattr(
                risk_service,
                "validate",
                None,
            )
        ):
            raise TypeError(
                "risk_service debe implementar validate()."
            )



        self.risk_service = (
            risk_service
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



    def get_risk_validation(
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



        result = self.risk_service.validate(
            market_context=market_context,
            market_data=market_data,
            account_state=account_state,
            risk_config=risk_config,
        )


        if (
            result.get("status")
            == "BLOCKED"
            and result.get("reason")
            == "INVALID_TRADE_PLAN"
        ):

            return None


        return result
