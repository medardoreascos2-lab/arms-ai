from __future__ import annotations

from typing import Any


class ReplayMarketDataBridgeV2:
    """
    Puente entre ReplayEngine y los consumidores
    de datos de mercado durante backtesting.
    """

    def __init__(
        self,
        *,
        market_data_hub_v2: Any | None = None,
    ) -> None:
        self.market_data_hub_v2 = (
            market_data_hub_v2
        )

    def publish(
        self,
        candle,
    ) -> dict[str, object]:

        if not hasattr(candle, "symbol"):
            raise TypeError(
                "candle inválido."
            )

        if not hasattr(candle, "close"):
            raise TypeError(
                "candle inválido."
            )

        if not hasattr(candle, "timeframe"):
            raise TypeError(
                "candle inválido."
            )

        if not hasattr(candle, "timestamp"):
            raise TypeError(
                "candle inválido."
            )

        if self.market_data_hub_v2 is not None:
            self.market_data_hub_v2.process_market_price(
                symbol=candle.symbol,
                current_price=candle.close,
                source="HISTORICAL_REPLAY",
                timeframe=candle.timeframe,
                timestamp=candle.timestamp,
            )

        return {
            "processed": True,
            "symbol": candle.symbol,
            "current_price": candle.close,
            "timestamp": candle.timestamp,
        }
