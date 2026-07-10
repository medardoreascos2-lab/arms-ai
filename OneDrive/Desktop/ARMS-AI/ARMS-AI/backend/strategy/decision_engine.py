class DecisionEngine:
    def __init__(self):
        self.decision = "ESPERAR"

    def analyze(self, trend, price, ema):
        if trend == "ALCISTA" and price > ema:
            self.decision = "BUSCAR COMPRAS"
        elif trend == "BAJISTA" and price < ema:
            self.decision = "BUSCAR VENTAS"
        else:
            self.decision = "ESPERAR"

        return self.decision

    def show(self):
        print("------ DECISION ENGINE ------")
        print(f"Decisión: {self.decision}")