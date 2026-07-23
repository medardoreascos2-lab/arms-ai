from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.break_even_engine import (
    BreakEvenEngine,
)
from backend.execution.partial_take_profit_engine import (
    PartialTakeProfitEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.position_monitor import (
    PositionMonitor,
)
from backend.execution.trailing_stop_engine import (
    TrailingStopEngine,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


class TradeManagementEngine:
    """
    Coordina la gestión completa de una posición:

    - Break Even
    - Trailing Stop
    - Stop Loss
    - Take Profit
    - Registro del trade cerrado
    """

    def __init__(
        self,
        *,
        position_manager: PositionManager,
        trade_history_store: TradeHistoryStore,
        point_value: float,
        break_even_trigger_points: float,
        break_even_offset_points: float,
        trailing_activation_points: float,
        trailing_distance_points: float,
        partial_trigger_points: float
        | None = None,
        partial_contracts_to_close: int
        | None = None,
    ) -> None:
        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        if not isinstance(
            position_manager,
            PositionManager,
        ):
            raise TypeError(
                "position_manager debe ser "
                "PositionManager."
            )

        if not isinstance(
            trade_history_store,
            TradeHistoryStore,
        ):
            raise TypeError(
                "trade_history_store debe ser "
                "TradeHistoryStore."
            )

        self.position_manager = (
            position_manager
        )

        self.trade_history_store = (
            trade_history_store
        )

        self.break_even_engine = (
            BreakEvenEngine(
                position_manager=(
                    position_manager
                ),
                trigger_points=(
                    break_even_trigger_points
                ),
                offset_points=(
                    break_even_offset_points
                ),
            )
        )

        self.trailing_stop_engine = (
            TrailingStopEngine(
                position_manager=(
                    position_manager
                ),
                activation_points=(
                    trailing_activation_points
                ),
                distance_points=(
                    trailing_distance_points
                ),
            )
        )

        self.partial_take_profit_engine = None

        if (
            partial_trigger_points
            is not None
            or partial_contracts_to_close
            is not None
        ):
            if (
                partial_trigger_points
                is None
                or partial_contracts_to_close
                is None
            ):
                raise ValueError(
                    "partial_trigger_points y "
                    "partial_contracts_to_close "
                    "deben proporcionarse juntos."
                )

            self.partial_take_profit_engine = (
                PartialTakeProfitEngine(
                    position_manager=(
                        position_manager
                    ),
                    trigger_points=(
                        partial_trigger_points
                    ),
                    contracts_to_close=(
                        partial_contracts_to_close
                    ),
                    point_value=point_value,
                )
            )

        self.position_monitor = (
            PositionMonitor(
                position_manager=(
                    position_manager
                ),
                point_value=point_value,
                trade_history_store=(
                    trade_history_store
                ),
                break_even_engine=(
                    self.break_even_engine
                ),
                trailing_stop_engine=(
                    self.trailing_stop_engine
                ),
            )
        )

    def evaluate_candle(
        self,
        *,
        symbol: str,
        timeframe: str,
        high: float,
        low: float,
        close: float,
        evaluated_at: datetime,
    ) -> dict[str, Any]:
        partial_take_profit = None

        if (
            self.partial_take_profit_engine
            is not None
        ):
            partial_take_profit = (
                self.partial_take_profit_engine
                .evaluate_price(
                    symbol=symbol,
                    timeframe=timeframe,
                    current_price=close,
                )
            )

        result = (
            self.position_monitor
            .evaluate_candle(
                symbol=symbol,
                timeframe=timeframe,
                high=high,
                low=low,
                close=close,
                evaluated_at=evaluated_at,
            )
        )

        if partial_take_profit is not None:
            result["partial_take_profit"] = (
                partial_take_profit
            )

        return result
