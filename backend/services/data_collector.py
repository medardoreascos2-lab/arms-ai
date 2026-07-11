from datetime import datetime, timedelta

from backend.models.candle import Candle


class DataCollector:
    def __init__(self, provider: str = "SIMULATED"):
        self.provider = provider

    def get_latest_candle(
        self,
        symbol: str = "NQ",
        timeframe: str = "1m",
    ) -> Candle:
        candles = self.get_historical_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=1,
        )
        return candles[-1]

    def get_historical_candles(
        self,
        symbol: str = "NQ",
        timeframe: str = "1m",
        limit: int = 100,
    ) -> list[Candle]:
        if self.provider != "SIMULATED":
            raise NotImplementedError(
                f"El proveedor {self.provider} todavía no está implementado."
            )

        if limit <= 0:
            raise ValueError("El límite de velas debe ser mayor que cero.")

        candles: list[Candle] = []
        base_price = 21500.0
        now = datetime.now()

        for index in range(limit):
            open_price = base_price + (index * 1.25)
            close_price = open_price + 0.75
            high_price = close_price + 2.0
            low_price = open_price - 1.5

            candle = Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=1000 + (index * 10),
                timestamp=now - timedelta(minutes=limit - index - 1),
            )

            candles.append(candle)

        return candles