from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.break_even_engine import (
    BreakEvenEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


class PositionMonitor:
    """
    Monitorea una posición abierta y la cierra
    automáticamente cuando alcanza el Stop Loss
    o el Take Profit.
    """

    def __init__(
        self,
        *,
        position_manager: PositionManager,
        point_value: float,
        trade_history_store:
        TradeHistoryStore
        | None = None,
        break_even_engine:
        BreakEvenEngine
        | None = None,
    ) -> None:
        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        self.position_manager = position_manager
        self.point_value = point_value
        self.trade_history_store = (
            trade_history_store
        )
        self.break_even_engine = (
            break_even_engine
        )

    def evaluate_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_price: float,
        evaluated_at: datetime,
    ) -> dict[str, Any]:

        position = self.position_manager.get_open_position(
            symbol=symbol,
            timeframe=timeframe,
        )

        if position is None:
            return {
                "status": "NO_POSITION",
                "closed": False,
            }

        break_even = None

        if (
            self.break_even_engine
            is not None
        ):
            break_even = (
                self.break_even_engine.evaluate_price(
                    symbol=symbol,
                    timeframe=timeframe,
                    current_price=current_price,
                )
            )

            position = (
                self.position_manager.get_open_position(
                    symbol=symbol,
                    timeframe=timeframe,
                )
            )

            if position is None:
                return {
                    "status": "NO_POSITION",
                    "closed": False,
                    "break_even": break_even,
                }

        side = position["side"]

        stop = position["stop_loss"]
        target = position["take_profit"]

        if side == "LONG":

            if current_price >= target:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=target,
                    closed_at=evaluated_at,
                    reason="TAKE_PROFIT",
                )

            if current_price <= stop:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=stop,
                    closed_at=evaluated_at,
                    reason="STOP_LOSS",
                )

        else:

            if current_price <= target:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=target,
                    closed_at=evaluated_at,
                    reason="TAKE_PROFIT",
                )

            if current_price >= stop:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=stop,
                    closed_at=evaluated_at,
                    reason="STOP_LOSS",
                )

        return {
            "status": "OPEN",
            "closed": False,
            "break_even": break_even,
            **position,
        }

    def _close_and_store(
        self,
        *,
        symbol: str,
        timeframe: str,
        exit_price: float,
        closed_at: datetime,
        reason: str,
    ) -> dict[str, Any]:
        closed_trade = (
            self.position_manager.close_position(
                symbol=symbol,
                timeframe=timeframe,
                exit_price=exit_price,
                closed_at=closed_at,
                reason=reason,
            )
        )

        if self.trade_history_store is not None:
            self.trade_history_store.append(
                closed_trade
            )

        return closed_trade

