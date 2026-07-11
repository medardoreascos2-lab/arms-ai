from datetime import datetime

from backend.models.candle import Candle


class DataCollector:
    def __init__(self, provider: str = "SIMULATED"):
        self.provider = provider

    def get_latest_candle(
        self,
        symbol: str = "NQ",
        timeframe: str = "1m",
    ) -> Candle:
        if self.provider != "SIMULATED":
            raise NotImplementedError(
                f"El proveedor {self.provider} todavía no está implementado."
            )

        return Candle(
            symbol=symbol,
            timeframe=timeframe,
            open=21500.00,
            high=21512.50,
            low=21494.25,
            close=21508.75,
            volume=1250,
            timestamp=datetime.now(),
        )