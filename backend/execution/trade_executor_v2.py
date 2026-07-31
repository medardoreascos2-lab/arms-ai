from __future__ import annotations

from backend.execution.position_v2 import (
    PositionDirectionV2,
    PositionV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class TradeExecutorV2:

    def __init__(self) -> None:
        self.active_position: PositionV2 | None = None
        self.closed_positions: list[PositionV2] = []

    def execute(
        self,
        *,
        decision: TradingDecisionV2,
        symbol: str,
        price: float,
        quantity: float,
    ) -> PositionV2 | None:

        if not isinstance(
            decision,
            TradingDecisionV2,
        ):
            raise TypeError(
                "decision debe ser TradingDecisionV2."
            )

        if not symbol.strip():
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if price <= 0:
            raise ValueError(
                "price debe ser mayor que cero."
            )

        if quantity <= 0:
            raise ValueError(
                "quantity debe ser mayor que cero."
            )

        if decision.action is TradingActionV2.HOLD:
            return None

        if self.active_position is not None:
            raise RuntimeError(
                "Ya existe una posición abierta."
            )

        direction = (
            PositionDirectionV2.LONG
            if decision.action is TradingActionV2.BUY
            else PositionDirectionV2.SHORT
        )

        position = PositionV2(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            quantity=quantity,
        )

        self.active_position = position

        return position

    def close_active_position(
        self,
        *,
        exit_price: float,
        reason: str,
    ) -> PositionV2:

        if self.active_position is None:
            raise RuntimeError(
                "No existe una posición activa."
            )

        self.active_position.close(
            exit_price=exit_price,
            reason=reason,
        )

        position = self.active_position

        self.closed_positions.append(
            position,
        )

        self.active_position = None

        return position
