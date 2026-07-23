from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.execution.break_even_engine import (
    BreakEvenEngine,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.trailing_stop_engine import (
    TrailingStopEngine,
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
        trailing_stop_engine:
        TrailingStopEngine
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
        self.trailing_stop_engine = (
            trailing_stop_engine
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
        high_price = float(high)
        low_price = float(low)
        close_price = float(close)

        if low_price > high_price:
            raise ValueError(
                "low no puede ser mayor que high."
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
            }

        side = str(
            position["side"]
        ).strip().upper()

        stop_loss = float(
            position["stop_loss"]
        )

        take_profit = float(
            position["take_profit"]
        )

        if side == "LONG":
            # Política conservadora:
            # si la vela toca SL y TP,
            # se considera primero el SL.
            if low_price <= stop_loss:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=stop_loss,
                    closed_at=evaluated_at,
                    reason="STOP_LOSS",
                )

            if high_price >= take_profit:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=take_profit,
                    closed_at=evaluated_at,
                    reason="TAKE_PROFIT",
                )

        elif side == "SHORT":
            # Política conservadora:
            # si la vela toca SL y TP,
            # se considera primero el SL.
            if high_price >= stop_loss:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=stop_loss,
                    closed_at=evaluated_at,
                    reason="STOP_LOSS",
                )

            if low_price <= take_profit:
                return self._close_and_store(
                    symbol=symbol,
                    timeframe=timeframe,
                    exit_price=take_profit,
                    closed_at=evaluated_at,
                    reason="TAKE_PROFIT",
                )

        else:
            raise ValueError(
                "side inválido."
            )

        return self.evaluate_price(
            symbol=symbol,
            timeframe=timeframe,
            current_price=close_price,
            evaluated_at=evaluated_at,
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

        trailing_stop = None

        if (
            self.trailing_stop_engine
            is not None
        ):
            trailing_stop = (
                self.trailing_stop_engine.evaluate_price(
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
                    "trailing_stop": (
                        trailing_stop
                    ),
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
            "trailing_stop": trailing_stop,
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

