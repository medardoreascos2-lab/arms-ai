from __future__ import annotations

from typing import Any

from backend.strategies.trading_strategy_v2 import (
    TradingDecisionV2,
    TradingStrategyV2,
)


class StrategyRunnerV2:
    """
    Ejecuta una estrategia de trading y valida
    que el resultado sea una TradingDecisionV2.
    """

    def __init__(
        self,
        *,
        strategy: TradingStrategyV2,
    ) -> None:

        if not isinstance(
            strategy,
            TradingStrategyV2,
        ):
            raise TypeError(
                "strategy debe ser una instancia de "
                "TradingStrategyV2."
            )

        self.strategy = strategy

    def run(
        self,
        context: Any,
    ) -> TradingDecisionV2:
        """
        Evalúa el contexto mediante la estrategia configurada.
        """

        decision = self.strategy.evaluate(context)

        if not isinstance(
            decision,
            TradingDecisionV2,
        ):
            raise TypeError(
                "La estrategia debe devolver "
                "TradingDecisionV2."
            )

        return decision
