from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock


@dataclass(slots=True)
class MarketState:
    symbol: str
    timeframe: str
    last_price: float
    timestamp: datetime


class MarketStateEngineV2:
    """
    Mantiene el último estado conocido del mercado.

    Este componente será utilizado por:

    - Trend Engine
    - Liquidity Engine
    - Smart Money
    - Probability Engine
    - Dashboard
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[
            tuple[str, str],
            MarketState,
        ] = {}

    def update(
        self,
        *,
        symbol: str,
        timeframe: str,
        price: float,
        timestamp: datetime,
    ) -> None:

        with self._lock:
            self._states[
                (
                    symbol,
                    timeframe,
                )
            ] = MarketState(
                symbol=symbol,
                timeframe=timeframe,
                last_price=price,
                timestamp=timestamp,
            )

    def get(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> MarketState | None:

        with self._lock:
            return self._states.get(
                (
                    symbol,
                    timeframe,
                )
            )

    def snapshot(self):

        with self._lock:
            return {
                key: value
                for key, value in self._states.items()
            }
