
from __future__ import annotations



class TradePlanDashboardProviderV2:
    """
    Provider encargado de exponer el plan de trading
    generado para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        trade_plan_service,
        market_context_provider=None,
        market_data_provider=None,
        risk_config_provider=None,
    ):


        if not callable(
            getattr(
                trade_plan_service,
                "generate",
                None,
            )
        ):
            raise TypeError(
                "trade_plan_service debe implementar generate()."
            )


        self.trade_plan_service = (
            trade_plan_service
        )


        self.market_context_provider = (
            market_context_provider
        )


        self.market_data_provider = (
            market_data_provider
        )


        self.risk_config_provider = (
            risk_config_provider
        )



    def get_trade_plan(
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



        if self.risk_config_provider:

            risk_config = (
                self.risk_config_provider()
            )

        else:

            risk_config = {
                "stop_points": 50,
                "risk_reward": 2,
            }



        result = self.trade_plan_service.generate(
            market_context=market_context,
            market_data=market_data,
            risk_config=risk_config,
        )


        if result is None:

            return None



        if (
            result.get("status")
            == "BLOCKED"
            and result.get("reason")
            == "DECISION_NOT_EXECUTE"
        ):

            return None


        return result
