from typing import Any

from backend.connectors.data_feed import DataFeed
from backend.market import MarketData
from backend.services.candle_manager import CandleManager


class BacktestMarketStage:
    """
    Prepara el contexto de mercado usando una ventana histórica
    proporcionada por BacktestEngine.

    A diferencia de MarketStage, no consulta DataCollector.
    """

    def __init__(
        self,
        max_candles: int = 500,
    ) -> None:
        if max_candles <= 0:
            raise ValueError(
                "max_candles debe ser mayor que cero."
            )

        self.max_candles = max_candles

    def run(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if "backtest_candles" not in context:
            raise KeyError(
                "BacktestMarketStage requiere "
                "'backtest_candles'."
            )

        candles = context["backtest_candles"]

        if not candles:
            raise ValueError(
                "La lista backtest_candles está vacía."
            )

        candle_manager = CandleManager(
            max_candles=self.max_candles,
        )

        for candle in candles:
            candle_manager.add_candle(candle)

        latest_candle = (
            candle_manager.get_latest_candle()
        )

        if latest_candle is None:
            raise RuntimeError(
                "No hay velas disponibles para el backtest."
            )

        current_price = latest_candle.close
        current_volume = latest_candle.volume

        market = MarketData(
            symbol=latest_candle.symbol,
            verbose=False,
        )
        market.update_price(current_price)

        feed = DataFeed(
            symbol=latest_candle.symbol,
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
