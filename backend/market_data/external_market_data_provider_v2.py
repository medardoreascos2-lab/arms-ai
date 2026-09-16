from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExternalMarketDataQuoteV2:
    symbol: str
    price: float
    source: str
    timeframe: str
    timestamp: datetime


@runtime_checkable
class ExternalMarketDataProviderV2(Protocol):
    """
    Boundary implemented by concrete external market-data adapters.

    The ARMS AI market-data core depends on this contract rather than
    directly depending on NinjaTrader or any other external platform.
    """

    @property
    def provider_name(self) -> str:
        ...

    def get_quote(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> ExternalMarketDataQuoteV2:
        ...
