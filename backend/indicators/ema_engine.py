class EMAEngine:
    def __init__(self, period=50):
        self.period = period
        self.ema = None

    def calculate(self, prices):
        if len(prices) < self.period:
            raise ValueError(
                f"Se necesitan al menos {self.period} precios para calcular la EMA."
            )

        multiplier = 2 / (self.period + 1)

        # Usamos una media simple inicial como semilla.
        ema_value = sum(prices[: self.period]) / self.period

        for price in prices[self.period :]:
            ema_value = (price - ema_value) * multiplier + ema_value

        self.ema = ema_value
        return self.ema

    def show(self):
        print("------ EMA ENGINE ------")
        print(f"EMA {self.period}: {self.ema:.2f}")