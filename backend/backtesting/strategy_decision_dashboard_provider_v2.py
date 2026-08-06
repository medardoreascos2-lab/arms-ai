
from __future__ import annotations



class StrategyDecisionDashboardProviderV2:
    """
    Provider encargado de exponer la decisión
    estratégica final para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        decision_service=None,
        strategy_decision_service=None,
        market_context_provider=None,
    ):


        if decision_service is None and strategy_decision_service is None:
            raise TypeError(
                "Debe existir decision_service o strategy_decision_service."
            )


        if decision_service is not None:

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


        if strategy_decision_service is not None:

            if not callable(
                getattr(
                    strategy_decision_service,
                    "get_decision",
                    None,
                )
            ):
                raise TypeError(
                    "strategy_decision_service debe implementar get_decision()."
                )


        self.decision_service = (
            decision_service
        )


        self.strategy_decision_service = (
            strategy_decision_service
        )


        self.market_context_provider = (
            market_context_provider
        )



    def get_decision(
        self,
        *,
        market_context=None,
    ) -> dict | None:



        if market_context is None:

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



        if self.strategy_decision_service is not None:

            return (
                self.strategy_decision_service
                .get_decision(
                    market_context=market_context,
                )
            )


        return self.decision_service.decide(
            market_context=market_context,
        )
