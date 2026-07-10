class EMAEngine:

    def __init__(self, period=50):
        self.period = period
        self.ema = None

    def calculate(self, prices):

        if len(prices) < self.period:
            print("No hay suficientes datos para calcular la EMA.")
            return None

        self.ema = sum(prices[-self.period:]) / self.period
        return self.ema

    def show(self):
        print("------ EMA ENGINE ------")
        print(f"EMA {self.period}: {self.ema}")