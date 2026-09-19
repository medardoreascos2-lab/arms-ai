from __future__ import annotations

from typing import Any
from collections.abc import Sequence

from backend.models.candle import Candle

from backend.backtesting.backtest_execution_simulator_v2 import (
    BacktestExecutionSimulatorV2,
)

from backend.backtesting.backtest_risk_adapter_factory_v2 import (
    BacktestRiskAdapterFactoryV2,
)

from backend.accounts.account_config_manager_v2 import (
    AccountConfigManagerV2,
)

from backend.backtesting.backtest_execution_adapter_v2 import (
    BacktestExecutionAdapterV2,
)

from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)

from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)


from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)

class _CandleView(Sequence):
    """Read-only indexing view; slicing never copies the underlying candles."""

    def __init__(self, candles, indices=None):
        self._candles = candles
        self._indices = range(len(candles)) if indices is None else indices

    def __len__(self):
        return len(self._indices)

    def __getitem__(self, index):
        selected = self._indices[index]
        if isinstance(index, slice):
            return _CandleView(self._candles, selected)
        return self._candles[selected]


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
        analysis_window: int = 50,
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

        self.account_config = (
            AccountConfigManagerV2()
        )


        self.risk_pipeline = (
            BacktestRiskAdapterFactoryV2.create(
                account_config=self.account_config,
            )
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

        self.analysis_window = int(
            analysis_window
        )

        if self.analysis_window <= 0:
            raise ValueError(
                "analysis_window debe ser mayor que cero."
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

        self.simulated_trades: list[
            object
        ] = []

        self.position_update_results: list[
            dict[str, object]
        ] = []

        self.active_position_id: str | None = None
        self.candle_history: list[dict[str, object]] = []

        self.future_candles = []
        self._has_run = False

    def run(self, *, execution_candles=None, minimum_candles: int = 1) -> int:
        """
        Ejecuta la sesión completa de backtesting.

        Devuelve la cantidad de velas procesadas.

        execution_candles selects the explicit single-pass mode. Its chronological
        snapshot must match the loaded replay (the production adapter ensures this).
        Warm-up builds history only; the final candle updates positions only.
        A fresh composition is required because strategies/lifecycles own state
        which cannot safely be reset by clearing the session's output lists.
        """

        if execution_candles is not None:
            if self._has_run:
                raise RuntimeError("Single-pass execution requires a fresh session.")
            if minimum_candles <= 0:
                raise ValueError("minimum_candles must be positive.")
        self._has_run = True

        self.decisions.clear()
        self.trade_plans.clear()
        self.signals.clear()
        self.submission_results.clear()
        self.simulated_trades.clear()
        self.position_update_results.clear()
        self.active_position_id = None
        self.candle_history.clear()

        def on_candle(
                candle: Any,
                publish_result: Any,
            ) -> None:

            normalized_candle = self._normalize_candle(
                candle
            )

            self._update_active_position_if_configured(
                candle=normalized_candle,
            )

            self.candle_history.append(
                normalized_candle
            )

            if execution_candles is not None and (
                len(self.candle_history) < minimum_candles
                or len(self.candle_history) == len(execution_candles)
            ):
                return

            analysis_history = (
                self.candle_history[
                    -self.analysis_window:
                ]
            )

            context = {
                "candle": normalized_candle,
                "history": analysis_history,
                "history_15m": analysis_history,
                "history_1h": analysis_history,

                # Monotonic candle clock for stateful strategy controls.
                #
                # This must remain independent from any bounded analytical
                # history window.  SignalControllerV2 cooldown is expressed
                # in bars, so its clock must advance once per market candle.
                "signal_index": len(self.candle_history),

                "publish_result": publish_result,

                "active_position_id": (
                    self.active_position_id
                ),

                "has_active_position": (
                    self.active_position_id
                    is not None
                ),
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

            submission_result = self._generate_signal_if_configured(
                decision=decision,
                candle=normalized_candle,
            )

            # A configured submission target is authoritative for this decision.
            # Missing or malformed acceptance must never reach the simulator.
            if self.signal_submission_target_v2 is not None and not (
                isinstance(submission_result, dict)
                and submission_result.get("accepted") is True
            ):
                return

            if execution_candles is not None:
                self.future_candles = _CandleView(
                    execution_candles,
                    range(len(self.candle_history), len(execution_candles)),
                )

            self._execute_trade_if_configured(
                decision=decision,
                candle=normalized_candle,
            )
        candles_processed = self.backtest_runner_v2.run(
            on_candle=on_candle,
        )

        return int(
            candles_processed
        )

    def build_report(
        self,
        *,
        candles_processed: int,
    ) -> BacktestReportV2:
        """
        Construye un reporte consolidado con los
        resultados actuales de la sesión.
        """

        normalized_candles_processed = int(
            candles_processed
        )

        if normalized_candles_processed < 0:
            raise ValueError(
                "candles_processed no puede ser negativo."
            )

        trade_history: list[dict[str, object]] = []
        performance_metrics: dict[str, object] = {}
        active_positions: list[dict[str, object]] = []

        target = self.signal_submission_target_v2

        if target is not None:
            get_trade_history = getattr(
                target,
                "get_trade_history",
                None,
            )

            if callable(get_trade_history):
                trade_history = list(
                    get_trade_history()
                )

            get_performance_metrics = getattr(
                target,
                "get_performance_metrics",
                None,
            )

            if callable(get_performance_metrics):
                performance_metrics = dict(
                    get_performance_metrics()
                )

            get_active_positions = getattr(
                target,
                "get_active_positions",
                None,
            )

            if callable(get_active_positions):
                active_positions = list(
                    get_active_positions()
                )

        return BacktestReportV2(
            candles_processed=(
                normalized_candles_processed
            ),
            decisions=list(
                self.decisions
            ),
            trade_plans=list(
                self.trade_plans
            ),
            signals=list(
                self.signals
            ),
            submission_results=list(
                self.submission_results
            ),
            position_updates=list(
                self.position_update_results
            ),
            trade_history=trade_history,
            performance_metrics=(
                performance_metrics
            ),
            active_positions=active_positions,
        )

    @staticmethod
    def _normalize_candle(
        candle: Any,
    ) -> dict[str, Any]:
        """
        Normaliza velas representadas como dict o Candle
        al formato interno utilizado por el backtesting.
        """

        if isinstance(candle, dict):
            return candle

        if isinstance(candle, Candle):
            return {
                "symbol": candle.symbol,
                "timeframe": candle.timeframe,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "timestamp": candle.timestamp,
            }

        raise TypeError(
            "candle debe ser un dict o una instancia "
            "de Candle."
        )

    def _generate_signal_if_configured(
        self,
        *,
        decision: TradingDecisionV2,
        candle: dict[str, Any],
    ) -> dict[str, Any] | None:

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

        trade_plan_decision = decision

        # The canonical strategy runner intentionally does not own position
        # sizing.  When contracts are absent, resolve the requested backtest
        # quantity through the session's existing risk authority before
        # building the TradePlan.  The downstream lifecycle still applies
        # its own authoritative risk cap to the submitted signal.
        if decision.metadata.get("contracts") is None:
            price = float(
                candle.get(
                    "close",
                    0.0,
                )
            )

            if price <= 0:
                raise ValueError(
                    "candle debe contener close válido "
                    "para evaluar sizing."
                )

            stop_loss = decision.metadata.get(
                "stop_loss"
            )

            if stop_loss is None:
                raise ValueError(
                    "La decisión debe contener stop_loss "
                    "para evaluar sizing."
                )

            profile = (
                self.account_config.get_active_account()
            )

            point_value = float(
                InstrumentProfileEngine()
                .get_profile(
                    symbol=symbol
                )["point_value"]
            )

            risk_result = (
                self.risk_pipeline.evaluate(
                    account_balance=float(
                        profile.account_size
                    ),
                    risk_percent=float(
                        profile.risk_percent
                    ),
                    stop_points=abs(
                        price - float(stop_loss)
                    ),
                    point_value=point_value,
                    daily_pnl=0.0,
                    total_drawdown=0.0,
                    open_positions=(
                        1
                        if self.active_position_id
                        else 0
                    ),
                    symbol=symbol,
                )
            )

            if not risk_result.allowed:
                return

            trade_plan_decision = TradingDecisionV2(
                action=decision.action,
                confidence=decision.confidence,
                reason=decision.reason,
                metadata={
                    **dict(
                        decision.metadata
                    ),
                    "contracts": int(
                        risk_result.contracts
                    ),
                },
            )

        trade_plan = (
            self.backtest_trade_plan_adapter_v2.build_trade_plan(
                decision=trade_plan_decision,
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


            simulated_trade = getattr(
                submission_result,
                "simulated_trade",
                None,
            )


            if simulated_trade is not None:
                self.simulated_trades.append(
                    simulated_trade
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

                active_position_id = None


                if isinstance(
                    submission_result,
                    dict,
                ):

                    active_position_id = (
                        submission_result.get(
                            "active_position_id"
                        )
                    )


                else:

                    active_position_id = getattr(
                        submission_result,
                        "active_position_id",
                        None,
                    )

                if (
                    accepted
                    and active_position_id
                    is not None
                ):
                    self.active_position_id = str(
                        active_position_id
                    ).strip()

            return submission_result

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
                "candle debe contener close válido."
            )


        is_long = (
            decision.action.value == "BUY"
        )


        if hasattr(
            self.trade_executor_v2,
            "future_candles",
        ):

            self.trade_executor_v2.future_candles = (
                self.future_candles
            )


        stop_loss = decision.metadata.get(
            "stop_loss"
        )

        if stop_loss is None:
            raise ValueError(
                "La decisión debe contener stop_loss "
                "para evaluar riesgo."
            )

        profile = (
            self.account_config.get_active_account()
        )

        point_value = float(
            InstrumentProfileEngine()
            .get_profile(
                symbol=symbol
            )["point_value"]
        )

        risk_result = (
            self.risk_pipeline.evaluate(
                account_balance=float(
                    profile.account_size
                ),
                risk_percent=float(
                    profile.risk_percent
                ),
                stop_points=abs(
                    price - float(stop_loss)
                ),
                point_value=point_value,
                daily_pnl=0.0,
                total_drawdown=0.0,
                open_positions=0,
                symbol=symbol,
            )
        )


        if not risk_result.allowed:

            return None



        simulated_trade = (
            self.trade_executor_v2.execute(
                symbol=symbol,
                direction=(
                    "BUY"
                    if is_long
                    else "SELL"
                ),
                entry=price,
                stop_loss=decision.metadata.get(
                    "stop_loss"
                ),

                take_profit=decision.metadata.get(
                    "take_profit"
                ),
                contracts=(
                    risk_result.contracts
                ),
                risk_amount=(
                    risk_result.risk_amount
                ),
                approved=True,
            )
        )


        self.simulated_trades.append(
            simulated_trade
        )


        self.submission_results.append(
            simulated_trade
        )
