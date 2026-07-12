from backend.models.candle import Candle


class LiquidityEngine:
    def __init__(self, tolerance: float = 1.0):
        if tolerance <= 0:
            raise ValueError("La tolerancia debe ser mayor que cero.")

        self.tolerance = tolerance
        self.equal_highs = False
        self.equal_lows = False
        self.sweep_detected = "NO"
        self.sweep_direction = "NINGUNA"
        self.liquidity_level: float | None = None

    def analyze(self, candles: list[Candle]) -> str:
        if len(candles) < 4:
            raise ValueError(
                "Se necesitan al menos 4 velas para analizar liquidez."
            )

        first = candles[-4]
        second = candles[-3]
        previous = candles[-2]
        current = candles[-1]

        self.equal_highs = (
            abs(first.high - second.high) <= self.tolerance
        )

        self.equal_lows = (
            abs(first.low - second.low) <= self.tolerance
        )

        self.sweep_detected = "NO"
        self.sweep_direction = "NINGUNA"
        self.liquidity_level = None

        if (
            self.equal_highs
            and current.high > max(first.high, second.high)
            and current.close < max(first.high, second.high)
        ):
            self.sweep_detected = "SÍ"
            self.sweep_direction = "BAJISTA"
            self.liquidity_level = max(first.high, second.high)

        elif (
            self.equal_lows
            and current.low < min(first.low, second.low)
            and current.close > min(first.low, second.low)
        ):
            self.sweep_detected = "SÍ"
            self.sweep_direction = "ALCISTA"
            self.liquidity_level = min(first.low, second.low)

        return self.sweep_detected

    def show(self) -> None:
        print("------ LIQUIDITY ENGINE ------")
        print(
            f"Equal Highs: {'SÍ' if self.equal_highs else 'NO'}"
        )
        print(
            f"Equal Lows: {'SÍ' if self.equal_lows else 'NO'}"
        )
        print(f"Sweep detectado: {self.sweep_detected}")
        print(f"Dirección del sweep: {self.sweep_direction}")

        if self.liquidity_level is not None:
            print(
                f"Nivel de liquidez: "
                f"{self.liquidity_level:.2f}"
            )