from __future__ import annotations


class ReplayMarketDataBridgeV2:
    """
    Puente entre ReplayEngine y los consumidores
    de datos de mercado durante backtesting.
    """

    def publish(
        self,
        candle,
    ) -> dict[str, object]:

        return {
            "processed": True,
            "symbol": candle.symbol,
            "current_price": candle.close,
            "timestamp": candle.timestamp,
        }
