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
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
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
                "prepared_order": None,
                "execution": None,
                "position": None,
                "active_position_id": None,
            }

        prepared_order = (
            self.execution_manager.prepare_order(
                signal=signal,
                order_type=order_type,
            )
        )

        execution = (
            self.paper_execution_engine.execute(
                prepared_order=prepared_order,
            )
        )

        position: dict[str, object] | None = None
        active_position_id: str | None = None

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
            ).strip().upper()
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

        accepted = (
            bool(
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
                None
                if accepted
                else "execution_not_opened"
            ),
            "prepared_order": (
                prepared_order
            ),
            "execution": execution,
            "position": position,
            "active_position_id": (
                active_position_id
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
