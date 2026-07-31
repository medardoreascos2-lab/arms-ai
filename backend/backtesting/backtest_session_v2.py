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
    ejecuta la estrategia y almacena decisiones.

    Opcionalmente puede:

    - ejecutar trades mediante TradeExecutorV2;
    - construir trade plans;
    - generar señales compatibles con SignalGeneratorV2.
    """

    def __init__(
        self,
        *,
        backtest_runner_v2,
        strategy_runner_v2,
        trade_executor_v2=None,
        backtest_trade_plan_adapter_v2=None,
        signal_generator_v2=None,
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

        if (
            backtest_trade_plan_adapter_v2 is not None
            and not callable(
                getattr(
                    backtest_trade_plan_adapter_v2,
                    "build_trade_plan",
                    None,
                )
            )
        ):
            raise TypeError(
                "backtest_trade_plan_adapter_v2 debe "
                "implementar build_trade_plan()."
            )

        if (
            signal_generator_v2 is not None
            and not callable(
                getattr(
                    signal_generator_v2,
                    "generate",
                    None,
                )
            )
        ):
            raise TypeError(
                "signal_generator_v2 debe implementar generate()."
            )

        signal_pipeline_components = (
            backtest_trade_plan_adapter_v2,
            signal_generator_v2,
        )

        if (
            any(
                component is not None
                for component
                in signal_pipeline_components
            )
            and not all(
                component is not None
                for component
                in signal_pipeline_components
            )
        ):
            raise ValueError(
                "backtest_trade_plan_adapter_v2 y "
                "signal_generator_v2 deben configurarse juntos."
            )

        self.backtest_runner_v2 = (
            backtest_runner_v2
        )
        self.strategy_runner_v2 = (
            strategy_runner_v2
        )
        self.trade_executor_v2 = (
            trade_executor_v2
        )
        self.backtest_trade_plan_adapter_v2 = (
            backtest_trade_plan_adapter_v2
        )
        self.signal_generator_v2 = (
            signal_generator_v2
        )

        self.decisions: list[
            TradingDecisionV2
        ] = []

        self.trade_plans: list[
            dict[str, object]
        ] = []

        self.signals: list[
            dict[str, object]
        ] = []

    def run(self) -> int:
        """
        Ejecuta la sesión completa de backtesting.

        Devuelve la cantidad de velas procesadas.
        """

        self.decisions.clear()
        self.trade_plans.clear()
        self.signals.clear()

        def on_candle(
            candle: Any,
            publish_result: Any,
        ) -> None:

            context = {
                "candle": candle,
                "publish_result": publish_result,
            }

            decision = (
                self.strategy_runner_v2.run(
                    context
                )
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
                decision.action
                is TradingActionV2.HOLD
            ):
                return

            if not isinstance(
                candle,
                dict,
            ):
                raise TypeError(
                    "candle debe ser un dict "
                    "para ejecutar trades o "
                    "generar señales."
                )

            self._generate_signal_if_configured(
                decision=decision,
                candle=candle,
            )

            self._execute_trade_if_configured(
                decision=decision,
                candle=candle,
            )

        return self.backtest_runner_v2.run(
            on_candle=on_candle,
        )

    def _generate_signal_if_configured(
        self,
        *,
        decision: TradingDecisionV2,
        candle: dict[str, Any],
    ) -> None:

        if (
            self.backtest_trade_plan_adapter_v2
            is None
            or self.signal_generator_v2
            is None
        ):
            return

        symbol = str(
            candle.get(
                "symbol",
                "",
            )
        ).strip()

        if not symbol:
            raise ValueError(
                "candle debe contener symbol "
                "para generar señales."
            )

        timeframe = str(
            candle.get(
                "timeframe",
                "",
            )
        ).strip()

        if not timeframe:
            raise ValueError(
                "candle debe contener timeframe "
                "para generar señales."
            )

        trade_plan = (
            self.backtest_trade_plan_adapter_v2.build_trade_plan(
                decision=decision,
                candle=candle,
            )
        )

        trade_validation = {
            "approved": True,
            "status": "VALID",
            "decision": "ALLOW_EXECUTION",
            "blocking_reasons": [],
            "warnings": [],
        }

        signal = (
            self.signal_generator_v2.generate(
                symbol=symbol,
                timeframe=timeframe,
                trade_plan=trade_plan,
                trade_validation=(
                    trade_validation
                ),
            )
        )

        self.trade_plans.append(
            trade_plan
        )

        self.signals.append(
            signal
        )

    def _execute_trade_if_configured(
        self,
        *,
        decision: TradingDecisionV2,
        candle: dict[str, Any],
    ) -> None:

        if self.trade_executor_v2 is None:
            return

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
                "candle debe contener un close "
                "mayor que cero."
            )

        self.trade_executor_v2.execute(
            symbol=symbol,
            decision=decision,
            price=price,
            quantity=1.0,
        )
