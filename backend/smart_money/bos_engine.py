from backend.models.candle import Candle


class BOSEngine:
    def __init__(self):
        self.bos = "NO"
        self.direction = "NINGUNA"
        self.broken_level: float | None = None

    def analyze(self, candles: list[Candle]) -> str:
        if len(candles) < 4:
            raise ValueError(
                "Se necesitan al menos 4 velas para detectar BOS."
            )

        reference = candles[-3]
        previous = candles[-2]
        current = candles[-1]

        self.bos = "NO"
        self.direction = "NINGUNA"
        self.broken_level = None

        if current.close > reference.high and previous.close <= reference.high:
            self.bos = "SÍ"
            self.direction = "ALCISTA"
            self.broken_level = reference.high

        elif current.close < reference.low and previous.close >= reference.low:
            self.bos = "SÍ"
            self.direction = "BAJISTA"
            self.broken_level = reference.low

        return self.bos

    def show(self) -> None:
        print("------ BOS ENGINE ------")
        print(f"BOS detectado: {self.bos}")
        print(f"Dirección: {self.direction}")

        if self.broken_level is not None:
            print(f"Nivel roto: {self.broken_level:.2f}")