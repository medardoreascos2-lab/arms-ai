
from __future__ import annotations



class StrategyDecisionDashboardProviderV2:
    """
    Provider encargado de exponer la decisión
    estratégica final para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        decision_service,
        market_context_provider=None,
    ):


        if not callable(
            getattr(
                decision_service,
                "decide",
                None,
            )
        ):
            raise TypeError(
                "decision_service debe implementar decide()."
            )


        self.decision_service = (
            decision_service
        )


        self.market_context_provider = (
            market_context_provider
        )



    def get_decision(
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



        return self.decision_service.decide(
            market_context=market_context,
        )
