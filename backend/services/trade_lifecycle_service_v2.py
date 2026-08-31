from __future__ import annotations

from datetime import datetime, timezone

from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)

from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)
from backend.connectors.paper_broker_connector_v2 import (
    PaperBrokerConnectorV2,
)

from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


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
from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)

from backend.execution.order_validation_engine_v2 import (
    OrderValidationEngineV2,
)

from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)

from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)


from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import (
    TradeLifecycleDashboardEventPublisherV2,
)


from backend.dashboard.risk_dashboard_event_publisher_v2 import (
    RiskDashboardEventPublisherV2,
)


class TradeLifecycleServiceV2(
    SignalSubmissionTargetV2,
):
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
        instrument_profile_engine:
        InstrumentProfileEngine
        | None = None,
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
        trade_journal_v2:
        TradeJournalV2
        | None = None,
        dashboard_event_publisher_v2:
        TradeLifecycleDashboardEventPublisherV2
        | None = None,
        risk_dashboard_event_publisher_v2:
        RiskDashboardEventPublisherV2
        | None = None,
        oco_manager_v2:
        OCOManagerV2
        | None = None,
        protective_order_registry_v2:
        ProtectiveOrderRegistryV2
        | None = None,
        broker_connector_v2:
        BrokerConnectorV2
        | None = None,
        execution_risk_gate_v1:
        ExecutionRiskGateV1,
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

        self.instrument_profile_engine = (
            instrument_profile_engine
        )

        self.execution_manager = (
            execution_manager
        )

        self.paper_execution_engine = (
            paper_execution_engine
        )

        if (
            broker_connector_v2
            is not None
            and not isinstance(
                broker_connector_v2,
                BrokerConnectorV2,
            )
        ):
            raise TypeError(
                "broker_connector_v2 debe ser "
                "BrokerConnectorV2."
            )

        if broker_connector_v2 is None:
            broker_connector_v2 = (
                PaperBrokerConnectorV2(
                    execution_engine=(
                        paper_execution_engine
                    ),
                    account_id=(
                        "ARMS-PAPER-LIFECYCLE"
                    ),
                    starting_balance=(
                        normalized_starting_balance
                    ),
                )
            )

        self.broker_connector_v2 = (
            broker_connector_v2
        )

        if not (
            self.broker_connector_v2
            .is_connected
        ):
            self.broker_connector_v2.connect()

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


        if not isinstance(
            execution_risk_gate_v1,
            ExecutionRiskGateV1,
        ):
            raise TypeError(
                "execution_risk_gate_v1 es obligatorio "
                "y debe ser ExecutionRiskGateV1."
            )

        self.execution_risk_gate_v1 = (
            execution_risk_gate_v1
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

        if (
            trade_journal_v2
            is not None
            and not isinstance(
                trade_journal_v2,
                TradeJournalV2,
            )
        ):
            raise TypeError(
                "trade_journal_v2 debe ser "
                "TradeJournalV2."
            )

        self.trade_journal_v2 = (
            trade_journal_v2
        )


        if (
            dashboard_event_publisher_v2
            is not None
            and not isinstance(
                dashboard_event_publisher_v2,
                TradeLifecycleDashboardEventPublisherV2,
            )
        ):
            raise TypeError(
                "dashboard_event_publisher_v2 debe ser "
                "TradeLifecycleDashboardEventPublisherV2."
            )

        self.dashboard_event_publisher_v2 = (
            dashboard_event_publisher_v2
        )


        if (
            risk_dashboard_event_publisher_v2
            is not None
            and not isinstance(
                risk_dashboard_event_publisher_v2,
                RiskDashboardEventPublisherV2,
            )
        ):
            raise TypeError(
                "risk_dashboard_event_publisher_v2 debe ser "
                "RiskDashboardEventPublisherV2."
            )

        self.risk_dashboard_event_publisher_v2 = (
            risk_dashboard_event_publisher_v2
        )


        self.starting_balance = (
            normalized_starting_balance
        )

        if (
            oco_manager_v2
            is not None
            and not isinstance(
                oco_manager_v2,
                OCOManagerV2,
            )
        ):
            raise TypeError(
                "oco_manager_v2 debe ser "
                "OCOManagerV2."
            )

        self.oco_manager_v2 = (
            oco_manager_v2
            or OCOManagerV2()
        )

        if (
            protective_order_registry_v2
            is not None
            and not isinstance(
                protective_order_registry_v2,
                ProtectiveOrderRegistryV2,
            )
        ):
            raise TypeError(
                "protective_order_registry_v2 "
                "debe ser "
                "ProtectiveOrderRegistryV2."
            )

        self.protective_order_registry_v2 = (
            protective_order_registry_v2
            or ProtectiveOrderRegistryV2()
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

        normalized_symbol = (
            str(
                working_signal.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if (
            self.instrument_profile_engine
            is not None
        ):
            instrument_profile = (
                self.instrument_profile_engine.get_profile(
                    symbol=normalized_symbol,
                )
            )

            resolved_point_value = float(
                instrument_profile["point_value"]
            )

            if isinstance(risk_context, dict):
                risk_context = dict(
                    risk_context
                )
                risk_context["point_value"] = (
                    resolved_point_value
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

        trade_journal_summary = (
            self.trade_journal_v2.get_summary()
            if self.trade_journal_v2
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
                    symbol=str(
                        working_signal.get(
                            "symbol",
                            "",
                        )
                    ).strip().upper(),
                )
            )


            if (
                self.risk_dashboard_event_publisher_v2
                is not None
            ):
                risk_payload = dict(
                    risk_evaluation
                )

                risk_payload[
                    "trading_blocked"
                ] = not bool(
                    risk_evaluation.get(
                        "approved",
                        False,
                    )
                )

                self.risk_dashboard_event_publisher_v2.publish_risk_updated(
                    risk=risk_payload,
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

            requested_contracts = int(
                working_signal.get(
                    "contracts",
                    0,
                )
            )

            risk_allowed_contracts = int(
                risk_evaluation.get(
                    "contracts",
                    0,
                )
            )

            working_signal[
                "contracts"
            ] = min(
                requested_contracts,
                risk_allowed_contracts,
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


            if (
                self.risk_dashboard_event_publisher_v2
                is not None
            ):
                self.risk_dashboard_event_publisher_v2.publish_open_risk_updated(
                    open_risk=dict(
                        portfolio_risk_evaluation
                    ),
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
        # 5. BARRERA FINAL DE RIESGO
        # ======================================

        execution_risk_gate_result = None

        if not signal_blocked:
            if risk_evaluation is None:
                raise ValueError(
                    "execution_risk_gate_v1 requiere "
                    "risk_evaluation. Configure "
                    "risk_manager_v2 y risk_context."
                )

            gate_risk_amount = float(
                risk_evaluation.get(
                    "actual_risk",
                    risk_evaluation.get(
                        "risk_amount",
                        0.0,
                    ),
                )
            )

            gate_contracts = int(
                prepared_order.get(
                    "contracts",
                    working_signal.get(
                        "contracts",
                        0,
                    ),
                )
            )

            gate_direction = (
                str(
                    prepared_order.get(
                        "direction",
                        working_signal.get(
                            "direction",
                            "",
                        ),
                    )
                )
                .strip()
                .upper()
            )

            gate_side = (
                "BUY"
                if gate_direction
                in {
                    "LONG",
                    "BUY",
                }
                else (
                    "SELL"
                    if gate_direction
                    in {
                        "SHORT",
                        "SELL",
                    }
                    else gate_direction
                )
            )

            execution_risk_gate_result = (
                self.execution_risk_gate_v1
                .evaluate_trade(
                    symbol=str(
                        prepared_order.get(
                            "symbol",
                            working_signal.get(
                                "symbol",
                                "",
                            ),
                        )
                    ),
                    side=gate_side,
                    contracts=gate_contracts,
                    risk_amount=gate_risk_amount,
                )
            )

            if (
                execution_risk_gate_result.get(
                    "execution"
                )
                != "APPROVED"
            ):
                return {
                    "accepted": False,
                    "reason": (
                        "execution_risk_gate_blocked"
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
                    "execution_risk_gate": (
                        execution_risk_gate_result
                    ),
                    "prepared_order": (
                        prepared_order
                    ),
                    "execution": None,
                    "position": None,
                    "active_position_id": None,
                    "portfolio_summary": (
                        self.portfolio_manager_v2
                        .get_summary()
                        if self.portfolio_manager_v2
                        is not None
                        else None
                    ),
                }

        # ======================================
        # 6. EJECUTAR ORDEN MEDIANTE BROKER
        # ======================================

        execution = (
            self.broker_connector_v2.submit_order(
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

                protection = (
                    self.protective_order_registry_v2
                    .create_protection(
                        position_id=(
                            active_position_id
                        ),
                        broker_position_id=(
                            str(
                                opened_position.get(
                                    "broker_position_id",
                                    "",
                                )
                            ).strip()
                            or None
                        ),
                        symbol=str(
                            opened_position.get(
                                "symbol",
                                "",
                            )
                        ),
                        direction=str(
                            opened_position.get(
                                "direction",
                                "",
                            )
                        ),
                        quantity=float(
                            opened_position.get(
                                "quantity",
                                0.0,
                            )
                        ),
                        entry_price=float(
                            opened_position.get(
                                "entry_price",
                                0.0,
                            )
                        ),
                        stop_price=float(
                            opened_position.get(
                                "stop_loss",
                                0.0,
                            )
                        ),
                        take_profit_price=float(
                            opened_position.get(
                                "take_profit",
                                0.0,
                            )
                        ),
                        metadata={
                            "order_id": (
                                opened_position.get(
                                    "order_id"
                                )
                            ),
                            "execution_mode": (
                                execution.get(
                                    "execution_mode"
                                )
                            ),
                            "broker": (
                                execution.get(
                                    "broker"
                                )
                            ),
                        },
                    )
                )

                oco_group = (
                    self.oco_manager_v2
                    .create_group(
                        position_id=(
                            active_position_id
                        ),
                        stop_order_id=str(
                            protection[
                                "stop_order_id"
                            ]
                        ),
                        take_profit_order_id=str(
                            protection[
                                "take_profit_order_id"
                            ]
                        ),
                        metadata={
                            "symbol": (
                                protection.get(
                                    "symbol"
                                )
                            ),
                            "direction": (
                                protection.get(
                                    "direction"
                                )
                            ),
                            "protection_group_id": (
                                protection.get(
                                    "protection_group_id"
                                )
                            ),
                            "broker_position_id": (
                                protection.get(
                                    "broker_position_id"
                                )
                            ),
                        },
                    )
                )

                position[
                    "protection_group_id"
                ] = protection[
                    "protection_group_id"
                ]

                position[
                    "oco_group_id"
                ] = oco_group[
                    "oco_group_id"
                ]

                position[
                    "stop_order_id"
                ] = protection[
                    "stop_order_id"
                ]

                position[
                    "take_profit_order_id"
                ] = protection[
                    "take_profit_order_id"
                ]

                self._active_positions[
                    active_position_id
                ] = dict(
                    position
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

                if (
                    self.trade_journal_v2
                    is not None
                ):
                    self.trade_journal_v2.record_open_trade(
                        trade={
                            "trade_id": (
                                "journal-"
                                + active_position_id
                            ),
                            "position_id": (
                                active_position_id
                            ),
                            "symbol": str(
                                opened_position.get(
                                    "symbol",
                                    working_signal.get(
                                        "symbol",
                                        "",
                                    ),
                                )
                            ),
                            "direction": str(
                                opened_position.get(
                                    "direction",
                                    working_signal.get(
                                        "direction",
                                        "",
                                    ),
                                )
                            ),
                            "entry_price": float(
                                opened_position.get(
                                    "entry_price",
                                    working_signal.get(
                                        "entry_price",
                                        0.0,
                                    ),
                                )
                            ),
                            "quantity": float(
                                opened_position.get(
                                    "quantity",
                                    working_signal.get(
                                        "contracts",
                                        0,
                                    ),
                                )
                            ),
                            "stop_loss": (
                                opened_position.get(
                                    "stop_loss",
                                    working_signal.get(
                                        "stop_loss"
                                    ),
                                )
                            ),
                            "take_profit": (
                                opened_position.get(
                                    "take_profit",
                                    working_signal.get(
                                        "take_profit"
                                    ),
                                )
                            ),
                            "entry_time": (
                                datetime.now(
                                    timezone.utc
                                )
                            ),
                            "status": "OPEN",
                        },
                    )

                    trade_journal_summary = (
                        self.trade_journal_v2
                        .get_summary()
                    )


                if (
                    self.dashboard_event_publisher_v2
                    is not None
                ):
                    self.dashboard_event_publisher_v2.publish_trade_opened(
                        trade=dict(
                            opened_position
                        ),
                    )

                    if (
                        portfolio_summary
                        is not None
                    ):
                        self.dashboard_event_publisher_v2.publish_portfolio_updated(
                            portfolio=dict(
                                portfolio_summary
                            ),
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
            "execution_risk_gate": (
                execution_risk_gate_result
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
            "trade_journal_summary": (
                trade_journal_summary
            ),
        }




    def _sync_protection_and_oco_after_close(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        close_reason = (
            str(
                position.get(
                    "close_reason",
                    "",
                )
                or "MANUAL"
            )
            .strip()
            .upper()
        )

        protection_group_id = (
            str(
                position.get(
                    "protection_group_id",
                    "",
                )
                or ""
            )
            .strip()
        )

        oco_group_id = (
            str(
                position.get(
                    "oco_group_id",
                    "",
                )
                or ""
            )
            .strip()
        )

        if (
            not protection_group_id
            or not oco_group_id
        ):
            return {
                "synchronized": False,
                "status": "MISSING_GROUP_IDS",
                "close_reason": close_reason,
                "protection": None,
                "oco": None,
            }

        triggered_order_id = None

        if close_reason == "TAKE_PROFIT":
            triggered_order_id = (
                str(
                    position.get(
                        "take_profit_order_id",
                        "",
                    )
                    or ""
                )
                .strip()
            )
        elif close_reason == "STOP_LOSS":
            triggered_order_id = (
                str(
                    position.get(
                        "stop_order_id",
                        "",
                    )
                    or ""
                )
                .strip()
            )

        if triggered_order_id:
            protection_result = (
                self
                .protective_order_registry_v2
                .complete_protection(
                    protection_group_id=(
                        protection_group_id
                    ),
                    triggered_order_id=(
                        triggered_order_id
                    ),
                    reason=close_reason,
                )
            )

            oco_result = (
                self.oco_manager_v2
                .cancel_remaining(
                    oco_group_id=oco_group_id,
                    triggered_order_id=(
                        triggered_order_id
                    ),
                    reason=close_reason,
                )
            )

            return {
                "synchronized": True,
                "status": "COMPLETED",
                "close_reason": close_reason,
                "triggered_order_id": (
                    triggered_order_id
                ),
                "protection": (
                    protection_result
                ),
                "oco": oco_result,
            }

        protection_result = (
            self
            .protective_order_registry_v2
            .cancel_protection(
                protection_group_id=(
                    protection_group_id
                ),
                reason=close_reason,
            )
        )

        oco_result = (
            self.oco_manager_v2.cancel_group(
                oco_group_id=oco_group_id,
                reason=close_reason,
            )
        )

        return {
            "synchronized": True,
            "status": "CANCELLED",
            "close_reason": close_reason,
            "triggered_order_id": None,
            "protection": protection_result,
            "oco": oco_result,
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
            self._sync_protection_and_oco_after_close(
                position=dict(
                    updated_position
                ),
            )

            updated_position[
                "realized_pnl"
            ] = float(
                updated_position.get(
                    "total_pnl",
                    updated_position.get(
                        "realized_pnl",
                        0.0,
                    ),
                )
                or 0.0
            )

            trade_record = (
                self.trade_history_manager.record(
                    position=updated_position,
                )
            )

            # V40: synchronize the closed position with
            # the shared Portfolio and Trade Journal.
            if self.portfolio_manager_v2 is not None:
                self.portfolio_manager_v2.close_position(
                    position_id=normalized_position_id,
                    exit_price=float(
                        updated_position.get(
                            "exit_price",
                            current_price,
                        )
                    ),
                    realized_pnl=float(
                        updated_position.get(
                            "realized_pnl",
                            0.0,
                        )
                    ),
                )

            if self.trade_journal_v2 is not None:
                journal_trade_id = (
                    "journal-"
                    + normalized_position_id
                )

                point_value = updated_position.get(
                    "point_value"
                )

                if point_value is None:
                    profile = (
                        self.instrument_profile_engine
                        .get_profile(
                            symbol=(
                                str(
                                    updated_position.get(
                                        "symbol",
                                        current_position.get(
                                            "symbol",
                                            "",
                                        ),
                                    )
                                )
                                .strip()
                                .upper()
                            )
                        )
                    )

                    if isinstance(profile, dict):
                        point_value = profile.get(
                            "point_value"
                        )

                if point_value is None:
                    raise ValueError(
                        "point_value no pudo resolverse "
                        "para el instrumento cerrado."
                    )

                self.trade_journal_v2.close_trade(
                    trade_id=journal_trade_id,
                    result=str(
                        updated_position.get(
                            "close_reason",
                            "CLOSED",
                        )
                    ),
                    pnl=float(
                        updated_position.get(
                            "realized_pnl",
                            0.0,
                        )
                    ),
                    exit_price=float(
                        updated_position.get(
                            "exit_price",
                            current_price,
                        )
                    ),
                    exit_reason=str(
                        updated_position.get(
                            "close_reason",
                            "CLOSED",
                        )
                    ),
                    point_value=float(point_value),
                )

            self._active_positions.pop(
                normalized_position_id,
                None,
            )

            active_position_removed = True

            performance_metrics = (
                self.get_performance_metrics()
            )


            if (
                self.dashboard_event_publisher_v2
                is not None
            ):
                self.dashboard_event_publisher_v2.publish_trade_closed(
                    trade=dict(
                        updated_position
                    ),
                )

                self.dashboard_event_publisher_v2.publish_position_updated(
                    position=dict(
                        updated_position
                    ),
                )

                if (
                    performance_metrics
                    is not None
                ):
                    self.dashboard_event_publisher_v2.publish_portfolio_updated(
                        portfolio=dict(
                            performance_metrics
                        ),
                    )

        else:
            self._active_positions[
                normalized_position_id
            ] = dict(
                updated_position
            )

            if (
                self.dashboard_event_publisher_v2
                is not None
            ):
                self.dashboard_event_publisher_v2.publish_position_updated(
                    position=dict(
                        updated_position
                    ),
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

        current_position = dict(
            self._active_positions[
                position_id
            ]
        )

        previous_quantity = float(
            current_position.get(
                "quantity",
                0.0,
            )
            or 0.0
        )

        new_quantity = float(
            normalized_position.get(
                "quantity",
                previous_quantity,
            )
            or previous_quantity
        )

        quantity_reduced = (
            previous_quantity > 0
            and new_quantity > 0
            and new_quantity
            < previous_quantity
        )

        previous_stop_loss = (
            current_position.get(
                "stop_loss"
            )
        )

        previous_take_profit = (
            current_position.get(
                "take_profit"
            )
        )

        new_stop_loss = (
            normalized_position.get(
                "stop_loss"
            )
        )

        new_take_profit = (
            normalized_position.get(
                "take_profit"
            )
        )

        stop_changed = (
            new_stop_loss is not None
            and (
                previous_stop_loss is None
                or float(
                    new_stop_loss
                )
                != float(
                    previous_stop_loss
                )
            )
        )

        target_changed = (
            new_take_profit is not None
            and (
                previous_take_profit is None
                or float(
                    new_take_profit
                )
                != float(
                    previous_take_profit
                )
            )
        )

        order_id = (
            str(
                current_position.get(
                    "order_id",
                    "",
                )
            )
            .strip()
        )

        broker_position_id = (
            str(
                current_position.get(
                    "broker_position_id",
                    "",
                )
            )
            .strip()
        )

        partial_close_result = None

        if quantity_reduced:
            if not broker_position_id:
                raise RuntimeError(
                    "La posición local no tiene "
                    "broker_position_id."
                )

            closed_quantity = round(
                previous_quantity
                - new_quantity,
                10,
            )

            partial_price = float(
                normalized_position.get(
                    "partial_exit_price",
                    normalized_position.get(
                        "current_price",
                        current_position.get(
                            "current_price",
                            0.0,
                        ),
                    ),
                )
                or 0.0
            )

            if partial_price <= 0:
                raise RuntimeError(
                    "No existe un precio válido "
                    "para el cierre parcial."
                )

            partial_close_result = (
                self.broker_connector_v2
                .close_partial(
                    position_id=(
                        broker_position_id
                    ),
                    quantity=(
                        closed_quantity
                    ),
                    current_price=(
                        partial_price
                    ),
                    reason=(
                        str(
                            normalized_position.get(
                                "last_partial_reason",
                                "PARTIAL_TAKE_PROFIT",
                            )
                        )
                    ),
                )
            )

            if not (
                bool(
                    partial_close_result.get(
                        "closed",
                        False,
                    )
                )
                and bool(
                    partial_close_result.get(
                        "partial",
                        False,
                    )
                )
            ):
                raise RuntimeError(
                    "El broker rechazó el cierre "
                    "parcial: "
                    + str(
                        partial_close_result.get(
                            "reason",
                            partial_close_result.get(
                                "status",
                                "unknown_error",
                            ),
                        )
                    )
                )

            broker_remaining = float(
                partial_close_result.get(
                    "remaining_quantity",
                    0.0,
                )
            )

            if broker_remaining != new_quantity:
                raise RuntimeError(
                    "La cantidad restante del broker "
                    "no coincide con ARMS AI."
                )

        if (
            order_id
            and (
                stop_changed
                or target_changed
            )
        ):
            broker_result = (
                self.broker_connector_v2
                .modify_order(
                    order_id=order_id,
                    stop_loss=(
                        float(
                            new_stop_loss
                        )
                        if stop_changed
                        else None
                    ),
                    take_profit=(
                        float(
                            new_take_profit
                        )
                        if target_changed
                        else None
                    ),
                )
            )

            if not bool(
                broker_result.get(
                    "modified",
                    False,
                )
            ):
                raise RuntimeError(
                    "El broker rechazó la "
                    "modificación de protección: "
                    + str(
                        broker_result.get(
                            "reason",
                            broker_result.get(
                                "status",
                                "unknown_error",
                            ),
                        )
                    )
                )

        self._active_positions[
            position_id
        ] = normalized_position

        if (
            quantity_reduced
            and self.portfolio_manager_v2
            is not None
        ):
            realized_pnl = float(
                normalized_position.get(
                    "realized_pnl",
                    0.0,
                )
                or 0.0
            )

            previous_realized = float(
                current_position.get(
                    "realized_pnl",
                    0.0,
                )
                or 0.0
            )

            incremental_realized = round(
                realized_pnl
                - previous_realized,
                10,
            )

            self.portfolio_manager_v2.reduce_position(
                position_id=position_id,
                remaining_quantity=(
                    new_quantity
                ),
                current_price=float(
                    normalized_position.get(
                        "current_price",
                        normalized_position.get(
                            "partial_exit_price",
                            0.0,
                        ),
                    )
                    or 0.0
                ),
                realized_pnl=(
                    incremental_realized
                ),
            )

        return dict(
            normalized_position
        )

    def restore_active_position(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        """
        Restaura una posición abierta dentro del estado
        activo del servicio.

        La operación es idempotente cuando la posición
        existente contiene exactamente el mismo estado.
        """

        if not isinstance(
            position,
            dict,
        ):
            raise ValueError(
                "position debe ser un dict."
            )

        position_id = str(
            position.get(
                "position_id",
                "",
            )
        ).strip()

        if not position_id:
            raise ValueError(
                "position_id es obligatorio."
            )

        status = str(
            position.get(
                "status",
                "",
            )
        ).strip().upper()

        if status != "OPEN":
            raise ValueError(
                "Solo se pueden restaurar "
                "posiciones con status OPEN."
            )

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).strip().upper()

        if not symbol:
            raise ValueError(
                "symbol es obligatorio."
            )

        direction = str(
            position.get(
                "direction",
                "",
            )
        ).strip().upper()

        if direction not in {
            "LONG",
            "SHORT",
        }:
            raise ValueError(
                "direction debe ser LONG o SHORT."
            )

        try:
            quantity = float(
                position.get(
                    "quantity",
                    0.0,
                )
            )
        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "quantity debe ser numérico."
            ) from exc

        if quantity <= 0.0:
            raise ValueError(
                "quantity debe ser mayor que cero."
            )

        restored_position = dict(
            position
        )

        restored_position[
            "position_id"
        ] = position_id

        restored_position[
            "status"
        ] = status

        restored_position[
            "symbol"
        ] = symbol

        restored_position[
            "direction"
        ] = direction

        restored_position[
            "quantity"
        ] = quantity

        existing_position = (
            self._active_positions.get(
                position_id
            )
        )

        if existing_position is not None:
            if (
                dict(existing_position)
                == restored_position
            ):
                return dict(
                    existing_position
                )

            raise ValueError(
                "Ya existe una posición activa "
                "con el mismo position_id y "
                "un estado diferente."
            )

        self._active_positions[
            position_id
        ] = dict(
            restored_position
        )

        return dict(
            restored_position
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
