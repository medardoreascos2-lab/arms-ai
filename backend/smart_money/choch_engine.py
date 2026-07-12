from backend.models.candle import Candle


class CHoCHEngine:
    def __init__(self):
        self.choch = "NO"
        self.direction = "NINGUNA"
        self.broken_level: float | None = None

    def analyze(
        self,
        candles: list[Candle],
        market_structure: str,
    ) -> str:
        if len(candles) < 4:
            raise ValueError(
                "Se necesitan al menos 4 velas para detectar CHoCH."
            )

        reference = candles[-3]
        previous = candles[-2]
        current = candles[-1]

        self.choch = "NO"
        self.direction = "NINGUNA"
        self.broken_level = None

        if (
            market_structure == "ALCISTA"
            and current.close < reference.low
            and previous.close >= reference.low
        ):
            self.choch = "SÍ"
            self.direction = "BAJISTA"
            self.broken_level = reference.low

        elif (
            market_structure == "BAJISTA"
            and current.close > reference.high
            and previous.close <= reference.high
        ):
            self.choch = "SÍ"
            self.direction = "ALCISTA"
            self.broken_level = reference.high

        return self.choch

    def show(self) -> None:
        print("------ CHOCH ENGINE ------")
        print(f"CHoCH detectado: {self.choch}")
        print(f"Dirección: {self.direction}")

        if self.broken_level is not None:
            print(f"Nivel roto: {self.broken_level:.2f}")