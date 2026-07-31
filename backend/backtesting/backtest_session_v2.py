from __future__ import annotations

from typing import Any

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class BacktestSessionV2:
    """
    Orquesta una sesión completa de backtesting.

    Recibe cada vela procesada por BacktestRunnerV2,
    construye el contexto de estrategia, almacena
    las decisiones y puede enviarlas a un ejecutor.
    """

    def __init__(
        self,
        *,
        backtest_runner_v2,
        strategy_runner_v2,
        trade_executor_v2=None,
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

        if (
            trade_executor_v2 is not None
            and not callable(
                getattr(
                    trade_executor_v2,
                    "execute",
                    None,
                )
            )
        ):
            raise TypeError(
                "trade_executor_v2 debe implementar execute()."
            )

        self.backtest_runner_v2 = backtest_runner_v2
        self.strategy_runner_v2 = strategy_runner_v2
        self.trade_executor_v2 = trade_executor_v2

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

            self.decisions.append(
                decision
            )

            if (
                self.trade_executor_v2 is None
                or decision.action
                is TradingActionV2.HOLD
            ):
                return

            if not isinstance(
                candle,
                dict,
            ):
                raise TypeError(
                    "candle debe ser un dict para ejecutar trades."
                )

            symbol = str(
                candle.get(
                    "symbol",
                    "",
                )
            ).strip()

            if not symbol:
                raise ValueError(
                    "candle debe contener symbol."
                )

            price = float(
                candle.get(
                    "close",
                    0.0,
                )
            )

            if price <= 0:
                raise ValueError(
                    "candle debe contener un close mayor que cero."
                )

            self.trade_executor_v2.execute(
                symbol=symbol,
                decision=decision,
                price=price,
                quantity=1.0,
            )

        return self.backtest_runner_v2.run(
            on_candle=on_candle,
        )
