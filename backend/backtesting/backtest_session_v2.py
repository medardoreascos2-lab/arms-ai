from __future__ import annotations

from typing import Any

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)

from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
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
        signal_submission_target_v2=None,
        signal_order_type: str = "MARKET",
        signal_risk_context=None,
        signal_order_context=None,
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

        if (
            signal_submission_target_v2 is not None
            and not isinstance(
                signal_submission_target_v2,
                SignalSubmissionTargetV2,
            )
        ):
            raise TypeError(
                "signal_submission_target_v2 debe ser "
                "SignalSubmissionTargetV2."
            )

        normalized_signal_order_type = str(
            signal_order_type
        ).strip().upper()

        if not normalized_signal_order_type:
            raise ValueError(
                "signal_order_type no puede estar vacío."
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
        self.signal_submission_target_v2 = (
            signal_submission_target_v2
        )
        self.signal_order_type = (
            normalized_signal_order_type
        )
        self.signal_risk_context = (
            signal_risk_context
        )
        self.signal_order_context = (
            signal_order_context
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

        self.submission_results: list[
            dict[str, object]
        ] = []

        self.position_update_results: list[
            dict[str, object]
        ] = []

        self.active_position_id: str | None = None

    def run(self) -> int:
        """
        Ejecuta la sesión completa de backtesting.

        Devuelve la cantidad de velas procesadas.
        """

        self.decisions.clear()
        self.trade_plans.clear()
        self.signals.clear()
        self.submission_results.clear()
        self.position_update_results.clear()
        self.active_position_id = None

        def on_candle(
            candle: Any,
            publish_result: Any,
        ) -> None:

            self._update_active_position_if_configured(
                candle=candle,
            )

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

        if (
            self.signal_submission_target_v2
            is not None
        ):
            submission_result = (
                self.signal_submission_target_v2.submit_signal(
                    signal=signal,
                    order_type=self.signal_order_type,
                    risk_context=self.signal_risk_context,
                    order_context=self.signal_order_context,
                )
            )

            self.submission_results.append(
                submission_result
            )

            if isinstance(
                submission_result,
                dict,
            ):
                accepted = bool(
                    submission_result.get(
                        "accepted",
                        False,
                    )
                )

                active_position_id = (
                    submission_result.get(
                        "active_position_id"
                    )
                )

                if (
                    accepted
                    and active_position_id
                    is not None
                ):
                    self.active_position_id = str(
                        active_position_id
                    ).strip()

    def _update_active_position_if_configured(
        self,
        *,
        candle: Any,
    ) -> None:
        """
        Actualiza la posición activa con el precio de
        cada vela posterior a la entrada.
        """

        if not self.active_position_id:
            return

        update_position = getattr(
            self.signal_submission_target_v2,
            "update_position",
            None,
        )

        if not callable(update_position):
            return

        if not isinstance(candle, dict):
            raise TypeError(
                "candle debe ser un dict para "
                "actualizar posiciones."
            )

        current_price = float(
            candle.get(
                "close",
                0.0,
            )
        )

        if current_price <= 0:
            raise ValueError(
                "candle debe contener un close "
                "mayor que cero para actualizar "
                "posiciones."
            )

        update_result = update_position(
            position_id=self.active_position_id,
            current_price=current_price,
        )

        if not isinstance(update_result, dict):
            raise TypeError(
                "update_position debe devolver un dict."
            )

        self.position_update_results.append(
            update_result
        )

        position = update_result.get(
            "position"
        )

        if (
            isinstance(position, dict)
            and str(
                position.get(
                    "status",
                    "",
                )
            ).strip().upper()
            == "CLOSED"
        ):
            self.active_position_id = None

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
