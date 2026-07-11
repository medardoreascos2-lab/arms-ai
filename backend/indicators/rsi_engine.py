class RSIEngine:
    def __init__(self, period: int = 14):
        if period <= 0:
            raise ValueError("El período del RSI debe ser mayor que cero.")

        self.period = period
        self.rsi: float | None = None
        self.status = "SIN DATOS"

    def calculate(self, prices: list[float]) -> float:
        if len(prices) < self.period + 1:
            raise ValueError(
                f"Se necesitan al menos {self.period + 1} precios "
                f"para calcular el RSI {self.period}."
            )

        gains: list[float] = []
        losses: list[float] = []

        for index in range(1, len(prices)):
            change = prices[index] - prices[index - 1]

            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))

        average_gain = sum(gains[: self.period]) / self.period
        average_loss = sum(losses[: self.period]) / self.period

        for index in range(self.period, len(gains)):
            average_gain = (
                (average_gain * (self.period - 1)) + gains[index]
            ) / self.period

            average_loss = (
                (average_loss * (self.period - 1)) + losses[index]
            ) / self.period

        if average_loss == 0:
            self.rsi = 100.0
        else:
            relative_strength = average_gain / average_loss
            self.rsi = 100 - (100 / (1 + relative_strength))

        self._update_status()
        return self.rsi

    def _update_status(self) -> None:
        if self.rsi is None:
            self.status = "SIN DATOS"
        elif self.rsi >= 70:
            self.status = "SOBRECOMPRA"
        elif self.rsi <= 30:
            self.status = "SOBREVENTA"
        else:
            self.status = "NEUTRAL"

    def show(self) -> None:
        print("------ RSI ENGINE ------")

        if self.rsi is None:
            print("RSI: sin calcular")
            print("Estado: SIN DATOS")
            return

        print(f"RSI {self.period}: {self.rsi:.2f}")
        print(f"Estado: {self.status}")