class TrendAnalyzer:

    def __init__(self):
        self.trend = "LATERAL"

    def analyze(self, current_price, ema50):

        if current_price > ema50:
            self.trend = "ALCISTA"

        elif current_price < ema50:
            self.trend = "BAJISTA"

        else:
            self.trend = "LATERAL"

    def show(self):

        print("------ TREND ANALYZER ------")
        print(f"Tendencia detectada: {self.trend}")