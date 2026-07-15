from backend.models.candle import Candle


class ATREngine:
    def __init__(
        self,
        period: int = 14,
        low_threshold: float = 5.0,
        high_threshold: float = 15.0,
    ) -> None:
        if period <= 0:
            raise ValueError(
                "El período del ATR debe ser mayor que cero."
            )

        if low_threshold < 0:
            raise ValueError(
                "low_threshold no puede ser negativo."
            )

        if high_threshold <= low_threshold:
            raise ValueError(
                "high_threshold debe ser mayor que "
                "low_threshold."
            )

        self.period = period
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

        self.atr: float | None = None
        self.status = "SIN DATOS"

    def calculate(
        self,
        candles: list[Candle],
    ) -> float:
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

        atr_value = (
            sum(true_ranges[: self.period])
            / self.period
        )

        for true_range in true_ranges[self.period:]:
            atr_value = (
                (atr_value * (self.period - 1))
                + true_range
            ) / self.period

        self.atr = atr_value
        self._update_status()

        return self.atr

    def _update_status(self) -> None:
        if self.atr is None:
            self.status = "SIN DATOS"

        elif self.atr < self.low_threshold:
            self.status = "VOLATILIDAD BAJA"

        elif self.atr < self.high_threshold:
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
