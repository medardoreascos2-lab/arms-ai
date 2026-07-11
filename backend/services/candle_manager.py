from backend.models.candle import Candle


class CandleManager:
    def __init__(self, max_candles: int = 500):
        self.max_candles = max_candles
        self.candles: list[Candle] = []

    def add_candle(self, candle: Candle) -> None:
        self.candles.append(candle)

        if len(self.candles) > self.max_candles:
            self.candles.pop(0)

    def get_close_prices(self) -> list[float]:
        return [candle.close for candle in self.candles]

    def get_latest_candle(self) -> Candle | None:
        if not self.candles:
            return None

        return self.candles[-1]

    def show_status(self) -> None:
        print("------ CANDLE MANAGER ------")
        print(f"Velas almacenadas: {len(self.candles)}")
        print(f"Capacidad máxima: {self.max_candles}")