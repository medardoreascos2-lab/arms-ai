from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class PositionDirectionV2(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class PositionStatusV2(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class PositionV2:
    symbol: str
    direction: PositionDirectionV2
    entry_price: float
    quantity: float

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    status: PositionStatusV2 = PositionStatusV2.OPEN

    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None

    realized_pnl: float = 0.0

    def __post_init__(self) -> None:

        if not isinstance(
            self.direction,
            PositionDirectionV2,
        ):
            raise TypeError(
                "direction debe ser PositionDirectionV2."
            )

        if not self.symbol.strip():
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if self.quantity <= 0:
            raise ValueError(
                "quantity debe ser mayor que cero."
            )

    def close(
        self,
        *,
        exit_price: float,
        reason: str,
    ) -> float:

        if self.status is PositionStatusV2.CLOSED:
            raise RuntimeError(
                "La posición ya está cerrada."
            )

        self.exit_price = exit_price
        self.exit_reason = reason

        if self.direction is PositionDirectionV2.LONG:
            pnl = (
                exit_price
                - self.entry_price
            ) * self.quantity
        else:
            pnl = (
                self.entry_price
                - exit_price
            ) * self.quantity

        self.realized_pnl = pnl
        self.status = PositionStatusV2.CLOSED

        return pnl
