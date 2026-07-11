from backend.models.candle import Candle


class ATREngine:
    def __init__(self, period: int = 14):
        if period <= 0:
            raise ValueError("El período del ATR debe ser mayor que cero.")

        self.period = period
        self.atr: float | None = None
        self.status = "SIN DATOS"

    def calculate(self, candles: list[Candle]) -> float:
        if len(candles) < self.period + 1:
            raise ValueError(
                f"Se necesitan al menos {self.period + 1} velas "
                f"para calcular el ATR {self.period}."
            )

        true_ranges: list[float] = []

        for index in range(1, len(candles)):
            current = candles[index]
            previous = candles[index - 1]

            true_range = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )

            true_ranges.append(true_range)

        atr_value = sum(true_ranges[: self.period]) / self.period

        for true_range in true_ranges[self.period :]:
            atr_value = (
                (atr_value * (self.period - 1)) + true_range
            ) / self.period

        self.atr = atr_value
        self._update_status()
        return self.atr

    def _update_status(self) -> None:
        if self.atr is None:
            self.status = "SIN DATOS"
        elif self.atr < 5:
            self.status = "VOLATILIDAD BAJA"
        elif self.atr < 15:
            self.status = "VOLATILIDAD MEDIA"
        else:
            self.status = "VOLATILIDAD ALTA"

    def show(self) -> None:
        print("------ ATR ENGINE ------")

        if self.atr is None:
            print("ATR: sin calcular")
            print("Estado: SIN DATOS")
            return

        print(f"ATR {self.period}: {self.atr:.2f}")
        print(f"Estado: {self.status}")