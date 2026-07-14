from typing import Any

from backend.connectors.data_feed import DataFeed
from backend.market import MarketData
from backend.services.candle_manager import CandleManager
from backend.services.data_collector import DataCollector


class MarketStage:
    """
    Carga los datos del mercado y prepara el contexto base
    para las siguientes etapas de ARMS AI.
    """

    def __init__(
        self,
        collector: DataCollector,
        symbol: str,
        timeframe: str,
        candle_limit: int = 100,
        max_candles: int = 500,
    ) -> None:
        self.collector = collector
        self.symbol = symbol
        self.timeframe = timeframe
        self.candle_limit = candle_limit
        self.max_candles = max_candles

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        candles = self.collector.get_historical_candles(
            symbol=self.symbol,
            timeframe=self.timeframe,
            limit=self.candle_limit,
        )

        candle_manager = CandleManager(
            max_candles=self.max_candles
        )

        for candle in candles:
            candle_manager.add_candle(candle)

        latest_candle = candle_manager.get_latest_candle()

        if latest_candle is None:
            raise RuntimeError(
                "No hay velas disponibles para analizar."
            )

        current_price = latest_candle.close
        current_volume = latest_candle.volume

        market = MarketData(
            symbol=latest_candle.symbol
        )
        market.update_price(current_price)

        feed = DataFeed(
            symbol=latest_candle.symbol
        )
        feed.update(
            price=current_price,
            volume=current_volume,
            timeframe=latest_candle.timeframe,
        )

        context.update(
            {
                "candles": candles,
                "candle_manager": candle_manager,
                "latest_candle": latest_candle,
                "current_price": current_price,
                "current_volume": current_volume,
                "market": market,
                "feed": feed,
            }
        )

        return context
