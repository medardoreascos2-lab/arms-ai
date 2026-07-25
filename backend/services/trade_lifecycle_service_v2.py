from __future__ import annotations

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.exposure_manager_v2 import (
    ExposureManagerV2,
)
from backend.execution.portfolio_risk_engine_v2 import (
    PortfolioRiskEngineV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)

from backend.execution.order_validation_engine_v2 import (
    OrderValidationEngineV2,
)

from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


class TradeLifecycleServiceV2:
    """
    Orquesta el ciclo completo de una operación:

    señal
    → orden preparada
    → ejecución PAPER
    → posición
    → cierre
    → historial
    → métricas
    """

    def __init__(
        self,
        *,
        execution_manager: ExecutionManagerV2,
        paper_execution_engine: PaperExecutionEngineV2,
        position_manager: PositionManagerV2,
        trade_history_manager: TradeHistoryManagerV2,
        performance_analytics: PerformanceAnalyticsV2,
        starting_balance: float,
        risk_manager_v2:
        RiskManagerV2
        | None = None,
        order_validation_engine_v2:
        OrderValidationEngineV2
        | None = None,
        exposure_manager_v2:
        ExposureManagerV2
        | None = None,
        portfolio_risk_engine_v2:
        PortfolioRiskEngineV2
        | None = None,
        portfolio_manager_v2:
        PortfolioManagerV2
        | None = None,
    ) -> None:
        if not isinstance(
            execution_manager,
            ExecutionManagerV2,
        ):
            raise TypeError(
                "execution_manager debe ser "
                "ExecutionManagerV2."
            )

        if not isinstance(
            paper_execution_engine,
            PaperExecutionEngineV2,
        ):
            raise TypeError(
                "paper_execution_engine debe ser "
                "PaperExecutionEngineV2."
            )

        if not isinstance(
            position_manager,
            PositionManagerV2,
        ):
            raise TypeError(
                "position_manager debe ser "
                "PositionManagerV2."
            )

        if not isinstance(
            trade_history_manager,
            TradeHistoryManagerV2,
        ):
            raise TypeError(
                "trade_history_manager debe ser "
                "TradeHistoryManagerV2."
            )

        if not isinstance(
            performance_analytics,
            PerformanceAnalyticsV2,
        ):
            raise TypeError(
                "performance_analytics debe ser "
                "PerformanceAnalyticsV2."
            )

        normalized_starting_balance = float(
            starting_balance
        )

        if normalized_starting_balance <= 0:
            raise ValueError(
                "starting_balance debe ser "
                "mayor que cero."
            )

        self.execution_manager = (
            execution_manager
        )

        self.paper_execution_engine = (
            paper_execution_engine
        )

        self.position_manager = (
            position_manager
        )

        self.trade_history_manager = (
            trade_history_manager
        )

        self.performance_analytics = (
            performance_analytics
        )


        if (
            risk_manager_v2
            is not None
            and not isinstance(
                risk_manager_v2,
                RiskManagerV2,
            )
        ):
            raise TypeError(
                "risk_manager_v2 debe ser "
                "RiskManagerV2."
            )

        self.risk_manager_v2 = (
            risk_manager_v2
        )


        if (
            order_validation_engine_v2
            is not None
            and not isinstance(
                order_validation_engine_v2,
                OrderValidationEngineV2,
            )
        ):
            raise TypeError(
                "order_validation_engine_v2 debe ser "
                "OrderValidationEngineV2."
            )

        self.order_validation_engine_v2 = (
            order_validation_engine_v2
        )


        if (
            exposure_manager_v2
            is not None
            and not isinstance(
                exposure_manager_v2,
                ExposureManagerV2,
            )
        ):
            raise TypeError(
                "exposure_manager_v2 debe ser "
                "ExposureManagerV2."
            )

        self.exposure_manager_v2 = (
            exposure_manager_v2
        )


        if (
            portfolio_risk_engine_v2
            is not None
            and not isinstance(
                portfolio_risk_engine_v2,
                PortfolioRiskEngineV2,
            )
        ):
            raise TypeError(
                "portfolio_risk_engine_v2 debe ser "
                "PortfolioRiskEngineV2."
            )

        self.portfolio_risk_engine_v2 = (
            portfolio_risk_engine_v2
        )


        if (
            portfolio_manager_v2
            is not None
            and not isinstance(
                portfolio_manager_v2,
                PortfolioManagerV2,
            )
        ):
            raise TypeError(
                "portfolio_manager_v2 debe ser "
                "PortfolioManagerV2."
            )

        self.portfolio_manager_v2 = (
            portfolio_manager_v2
        )


        self.starting_balance = (
            normalized_starting_balance
        )

        self._active_positions: dict[
            str,
            dict[str, object],
        ] = {}

    def submit_signal(
        self,
        *,
        signal: dict[str, object],
        order_type: str,
        risk_context:
        dict[str, object]
        | None = None,
        order_context:
        dict[str, object]
        | None = None,
    ) -> dict[str, object]:
        if not isinstance(
            signal,
            dict,
        ):
            raise TypeError(
                "signal debe ser un dict."
            )

        if self._active_positions:
            return {
                "accepted": False,
                "reason": (
                    "position_already_open"
                ),
                "risk_evaluation": None,
                "exposure_evaluation": None,
                "portfolio_risk_evaluation": None,
                "order_validation": None,
                "prepared_order": None,
                "execution": None,
                "position": None,
                "active_position_id": None,
                "portfolio_summary": (
                    self.portfolio_manager_v2.get_summary()
                    if self.portfolio_manager_v2
                    is not None
                    else None
                ),
            }

        working_signal = dict(
            signal
        )


        signal_blocked = not bool(
            working_signal.get(
                "approved",
                False,
            )
        )

        risk_evaluation = None
        exposure_evaluation = None
        portfolio_risk_evaluation = None
        portfolio_summary = (
            self.portfolio_manager_v2.get_summary()
            if self.portfolio_manager_v2
            is not None
            else None
        )
        order_validation = None

        entry_price = 0.0
        stop_loss = 0.0
        stop_points = 0.0

        if not signal_blocked:
            entry_price = float(
                working_signal.get(
                    "entry_price",
                    0.0,
                )
            )

            stop_loss = float(
                working_signal.get(
                    "stop_loss",
                    0.0,
                )
            )

            stop_points = abs(
                entry_price
                - stop_loss
            )

            if stop_points <= 0:
                raise ValueError(
                    "stop_points debe ser "
                    "mayor que cero."
                )

        # ======================================
        # 1. EVALUACIÓN DE RIESGO
        # ======================================

        if (
            not signal_blocked
            and self.risk_manager_v2
            is not None
        ):
            if not isinstance(
                risk_context,
                dict,
            ):
                raise ValueError(
                    "risk_context debe ser "
                    "un dict cuando "
                    "risk_manager_v2 está "
                    "configurado."
                )

            required_risk_fields = [
                "account_balance",
                "risk_percent",
                "point_value",
                "daily_pnl",
                "total_drawdown",
            ]

            missing_risk_fields = [
                field
                for field
                in required_risk_fields
                if field not in risk_context
            ]

            if missing_risk_fields:
                raise ValueError(
                    "risk_context incompleto: "
                    + ", ".join(
                        missing_risk_fields
                    )
                )

            risk_evaluation = (
                self.risk_manager_v2.evaluate(
                    account_balance=float(
                        risk_context[
                            "account_balance"
                        ]
                    ),
                    risk_percent=float(
                        risk_context[
                            "risk_percent"
                        ]
                    ),
                    stop_points=stop_points,
                    point_value=float(
                        risk_context[
                            "point_value"
                        ]
                    ),
                    daily_pnl=float(
                        risk_context[
                            "daily_pnl"
                        ]
                    ),
                    total_drawdown=float(
                        risk_context[
                            "total_drawdown"
                        ]
                    ),
                    open_positions=len(
                        self._active_positions
                    ),
                )
            )

            if not bool(
                risk_evaluation.get(
                    "approved",
                    False,
                )
            ):
                return {
                    "accepted": False,
                    "reason": "risk_blocked",
                    "risk_evaluation": (
                        risk_evaluation
                    ),
                    "exposure_evaluation": None,
                    "portfolio_risk_evaluation": None,
                    "order_validation": None,
                    "prepared_order": None,
                    "execution": None,
                    "position": None,
                    "active_position_id": None,
                    "portfolio_summary": (
                        self.portfolio_manager_v2.get_summary()
                        if self.portfolio_manager_v2
                        is not None
                        else None
                    ),
                }

            working_signal[
                "contracts"
            ] = int(
                risk_evaluation[
                    "contracts"
                ]
            )

        # ======================================
        # 2. EVALUACIÓN DE EXPOSICIÓN
        # ======================================

        if (
            not signal_blocked
            and self.exposure_manager_v2
            is not None
        ):
            if not isinstance(
                risk_context,
                dict,
            ):
                raise ValueError(
                    "risk_context debe ser "
                    "un dict cuando "
                    "exposure_manager_v2 está "
                    "configurado."
                )

            if (
                "point_value"
                not in risk_context
            ):
                raise ValueError(
                    "risk_context incompleto: "
                    "point_value"
                )

            candidate_contracts = int(
                working_signal.get(
                    "contracts",
                    0,
                )
            )

            exposure_evaluation = (
                self.exposure_manager_v2.evaluate(
                    open_positions=(
                        self.get_active_positions()
                    ),
                    candidate_symbol=str(
                        working_signal.get(
                            "symbol",
                            "",
                        )
                    ),
                    candidate_contracts=(
                        candidate_contracts
                    ),
                    candidate_stop_points=(
                        stop_points
                    ),
                    candidate_point_value=float(
                        risk_context[
                            "point_value"
                        ]
                    ),
                )
            )

            if not bool(
                exposure_evaluation.get(
                    "approved",
                    False,
                )
            ):
                return {
                    "accepted": False,
                    "reason": "exposure_blocked",
                    "risk_evaluation": (
                        risk_evaluation
                    ),
                    "exposure_evaluation": (
                        exposure_evaluation
                    ),
                    "portfolio_risk_evaluation": None,
                    "order_validation": None,
                    "prepared_order": None,
                    "execution": None,
                    "position": None,
                    "active_position_id": None,
                    "portfolio_summary": (
                        self.portfolio_manager_v2.get_summary()
                        if self.portfolio_manager_v2
                        is not None
                        else None
                    ),
                }

        # ======================================
        # 3. EVALUACIÓN DE RIESGO DEL PORTAFOLIO
        # ======================================

        if (
            not signal_blocked
            and self.portfolio_risk_engine_v2
            is not None
        ):
            if not isinstance(
                risk_context,
                dict,
            ):
                raise ValueError(
                    "risk_context debe ser "
                    "un dict cuando "
                    "portfolio_risk_engine_v2 "
                    "está configurado."
                )

            required_portfolio_fields = [
                "point_value",
                "current_price",
            ]

            missing_portfolio_fields = [
                field
                for field
                in required_portfolio_fields
                if field not in risk_context
            ]

            if missing_portfolio_fields:
                raise ValueError(
                    "risk_context incompleto: "
                    + ", ".join(
                        missing_portfolio_fields
                    )
                )

            candidate_contracts = int(
                working_signal.get(
                    "contracts",
                    0,
                )
            )

            portfolio_risk_evaluation = (
                self.portfolio_risk_engine_v2.evaluate(
                    open_positions=(
                        self.get_active_positions()
                    ),
                    candidate_symbol=str(
                        working_signal.get(
                            "symbol",
                            "",
                        )
                    ),
                    candidate_direction=str(
                        working_signal.get(
                            "direction",
                            "",
                        )
                    ),
                    candidate_contracts=(
                        candidate_contracts
                    ),
                    candidate_entry_price=(
                        entry_price
                    ),
                    candidate_current_price=float(
                        risk_context[
                            "current_price"
                        ]
                    ),
                    candidate_stop_loss=(
                        stop_loss
                    ),
                    candidate_point_value=float(
                        risk_context[
                            "point_value"
                        ]
                    ),
                )
            )

            if not bool(
                portfolio_risk_evaluation.get(
                    "approved",
                    False,
                )
            ):
                return {
                    "accepted": False,
                    "reason": (
                        "portfolio_risk_blocked"
                    ),
                    "risk_evaluation": (
                        risk_evaluation
                    ),
                    "exposure_evaluation": (
                        exposure_evaluation
                    ),
                    "portfolio_risk_evaluation": (
                        portfolio_risk_evaluation
                    ),
                    "order_validation": None,
                    "prepared_order": None,
                    "execution": None,
                    "position": None,
                    "active_position_id": None,
                    "portfolio_summary": (
                        self.portfolio_manager_v2.get_summary()
                        if self.portfolio_manager_v2
                        is not None
                        else None
                    ),
                }

        # ======================================
        # 4. PREPARAR ORDEN
        # ======================================

        prepared_order = (
            self.execution_manager.prepare_order(
                signal=working_signal,
                order_type=order_type,
            )
        )

        # ======================================
        # 4. VALIDACIÓN FINAL DE ORDEN
        # ======================================

        if (
            not signal_blocked
            and self.order_validation_engine_v2
            is not None
        ):
            if not isinstance(
                order_context,
                dict,
            ):
                raise ValueError(
                    "order_context debe ser "
                    "un dict cuando "
                    "order_validation_engine_v2 "
                    "está configurado."
                )

            if (
                "market_is_open"
                not in order_context
            ):
                raise ValueError(
                    "order_context incompleto: "
                    "market_is_open"
                )

            open_symbols = {
                str(
                    position.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
                for position
                in self._active_positions.values()
                if str(
                    position.get(
                        "symbol",
                        "",
                    )
                ).strip()
            }

            order_validation = (
                self.order_validation_engine_v2
                .validate(
                    prepared_order=(
                        prepared_order
                    ),
                    market_is_open=bool(
                        order_context[
                            "market_is_open"
                        ]
                    ),
                    open_symbols=open_symbols,
                )
            )

            if not bool(
                order_validation.get(
                    "approved",
                    False,
                )
            ):
                return {
                    "accepted": False,
                    "reason": (
                        "order_validation_blocked"
                    ),
                    "risk_evaluation": (
                        risk_evaluation
                    ),
                    "exposure_evaluation": (
                        exposure_evaluation
                    ),
                    "order_validation": (
                        order_validation
                    ),
                    "prepared_order": (
                        prepared_order
                    ),
                    "execution": None,
                    "position": None,
                    "active_position_id": None,
                    "portfolio_summary": (
                        self.portfolio_manager_v2.get_summary()
                        if self.portfolio_manager_v2
                        is not None
                        else None
                    ),
                }

        # ======================================
        # 5. EJECUTAR ORDEN PAPER
        # ======================================

        execution = (
            self.paper_execution_engine.execute(
                prepared_order=prepared_order,
            )
        )

        position: dict[str, object] | None = None
        active_position_id: str | None = None

        # ======================================
        # 6. ABRIR POSICIÓN
        # ======================================

        if (
            bool(
                execution.get(
                    "accepted",
                    False,
                )
            )
            and str(
                execution.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
            == "FILLED"
        ):
            opened_position = (
                self.position_manager.open_position(
                    execution=execution,
                )
            )

            if bool(
                opened_position.get(
                    "opened",
                    False,
                )
            ):
                position = opened_position

                active_position_id = str(
                    opened_position[
                        "position_id"
                    ]
                )

                self._active_positions[
                    active_position_id
                ] = dict(
                    opened_position
                )


                if (
                    self.portfolio_manager_v2
                    is not None
                ):
                    self.portfolio_manager_v2.add_position(
                        position=opened_position,
                    )

                    portfolio_summary = (
                        self.portfolio_manager_v2
                        .get_summary()
                    )

        accepted = (
            not signal_blocked
            and bool(
                prepared_order.get(
                    "approved",
                    False,
                )
            )
            and bool(
                execution.get(
                    "accepted",
                    False,
                )
            )
            and position is not None
        )

        return {
            "accepted": accepted,
            "reason": (
                "signal_not_approved"
                if signal_blocked
                else (
                    None
                    if accepted
                    else "execution_not_opened"
                )
            ),
            "risk_evaluation": (
                risk_evaluation
            ),
            "exposure_evaluation": (
                exposure_evaluation
            ),
            "portfolio_risk_evaluation": (
                portfolio_risk_evaluation
            ),
            "order_validation": (
                order_validation
            ),
            "prepared_order": (
                prepared_order
            ),
            "execution": execution,
            "position": position,
            "active_position_id": (
                active_position_id
            ),
            "portfolio_summary": (
                portfolio_summary
            ),
        }




    def update_position(
        self,
        *,
        position_id: str,
        current_price: float,
    ) -> dict[str, object]:
        normalized_position_id = (
            str(position_id)
            .strip()
        )

        if not normalized_position_id:
            raise ValueError(
                "position_id es obligatorio."
            )

        if (
            normalized_position_id
            not in self._active_positions
        ):
            raise ValueError(
                "position_id no existe."
            )

        current_position = (
            self._active_positions[
                normalized_position_id
            ]
        )

        updated_position = (
            self.position_manager.update_position(
                position=current_position,
                current_price=current_price,
            )
        )

        trade_record = None
        active_position_removed = False
        performance_metrics = None

        updated_status = (
            str(
                updated_position.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if updated_status == "CLOSED":
            trade_record = (
                self.trade_history_manager.record(
                    position=updated_position,
                )
            )

            self._active_positions.pop(
                normalized_position_id,
                None,
            )

            active_position_removed = True

            performance_metrics = (
                self.get_performance_metrics()
            )

        else:
            self._active_positions[
                normalized_position_id
            ] = dict(
                updated_position
            )

        return {
            "updated": True,
            "position": updated_position,
            "trade_record": trade_record,
            "performance_metrics": (
                performance_metrics
            ),
            "active_position_removed": (
                active_position_removed
            ),
        }

    def replace_active_position(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            position,
            dict,
        ):
            raise TypeError(
                "position debe ser un dict."
            )

        position_id = (
            str(
                position.get(
                    "position_id",
                    "",
                )
            )
            .strip()
        )

        if not position_id:
            raise ValueError(
                "position_id es obligatorio."
            )

        if (
            position_id
            not in self._active_positions
        ):
            raise ValueError(
                "position_id no existe."
            )

        normalized_position = dict(
            position
        )

        self._active_positions[
            position_id
        ] = normalized_position

        return dict(
            normalized_position
        )

    def get_active_positions(
        self,
    ) -> list[dict[str, object]]:
        return [
            dict(
                position
            )
            for position
            in self._active_positions.values()
        ]

    def get_trade_history(
        self,
        *,
        limit: int | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, object]]:
        return (
            self.trade_history_manager.get_history(
                limit=limit,
                symbol=symbol,
            )
        )

    def get_performance_metrics(
        self,
    ) -> dict[str, object]:
        history = self.get_trade_history()

        return self.performance_analytics.analyze(
            trades=history,
            starting_balance=(
                self.starting_balance
            ),
        )
