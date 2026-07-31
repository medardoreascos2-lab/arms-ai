from __future__ import annotations

from typing import Any

from backend.strategies.trading_strategy_v2 import (
    TradingDecisionV2,
)


class BacktestSessionV2:
    """
    Orquesta una sesión de backtesting.

    Recibe cada vela procesada por BacktestRunnerV2,
    construye el contexto de estrategia y almacena
    las decisiones generadas.
    """

    def __init__(
        self,
        *,
        backtest_runner_v2,
        strategy_runner_v2,
    ) -> None:

        if not callable(
            getattr(
                backtest_runner_v2,
                "run",
                None,
            )
        ):
            raise TypeError(
                "backtest_runner_v2 debe implementar run()."
            )

        if not callable(
            getattr(
                strategy_runner_v2,
                "run",
                None,
            )
        ):
            raise TypeError(
                "strategy_runner_v2 debe implementar run()."
            )

        self.backtest_runner_v2 = backtest_runner_v2
        self.strategy_runner_v2 = strategy_runner_v2

        self.decisions: list[TradingDecisionV2] = []

    def run(self) -> int:
        """
        Ejecuta la sesión completa de backtesting.

        Devuelve la cantidad de velas procesadas.
        """

        self.decisions.clear()

        def on_candle(
            candle: Any,
            publish_result: Any,
        ) -> None:

            context = {
                "candle": candle,
                "publish_result": publish_result,
            }

            decision = self.strategy_runner_v2.run(
                context
            )

            if not isinstance(
                decision,
                TradingDecisionV2,
            ):
                raise TypeError(
                    "strategy_runner_v2 debe devolver "
                    "TradingDecisionV2."
                )

            self.decisions.append(decision)

        return self.backtest_runner_v2.run(
            on_candle=on_candle,
        )
