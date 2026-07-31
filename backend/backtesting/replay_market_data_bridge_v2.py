from __future__ import annotations

from backend.models.candle import Candle


class ReplayMarketDataBridgeV2:
    """
    Envía velas históricas al mismo pipeline utilizado
    por el mercado en tiempo real.
    """

    SOURCE = "HISTORICAL_REPLAY"

    def __init__(
        self,
        *,
        market_data_hub_v2,
    ) -> None:

        if (
            market_data_hub_v2 is None
            or not callable(
                getattr(
                    market_data_hub_v2,
                    "process_market_price",
                    None,
                )
            )
        ):
            raise TypeError(
                "market_data_hub_v2 debe implementar process_market_price()."
            )

        self.market_data_hub_v2 = (
            market_data_hub_v2
        )

    def publish(
        self,
        candle: Candle,
    ) -> dict[str, object]:

        if not isinstance(
            candle,
            Candle,
        ):
            raise TypeError(
                "candle debe ser una instancia de Candle."
            )

        return self.market_data_hub_v2.process_market_price(
            symbol=candle.symbol,
            current_price=candle.close,
            source=self.SOURCE,
            timeframe=candle.timeframe,
            timestamp=candle.timestamp,
        )
