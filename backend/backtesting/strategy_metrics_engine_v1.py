class StrategyMetricsEngineV1:
    """
    Calcula métricas de certificación
    de estrategia ARMS AI.
    """

    def __init__(self):
        self.results = []


    def add_result(
        self,
        scenario: str,
        action: str,
        score: float,
        probability: float,
        confidence: str,
        approved: bool,
    ):

        self.results.append(
            {
                "scenario": scenario,
                "action": action,
                "score": score,
                "probability": probability,
                "confidence": confidence,
                "approved": approved,
            }
        )


    def calculate(self):

        total = len(self.results)

        approved = sum(
            1
            for r in self.results
            if r["approved"]
        )

        buy_signals = sum(
            1
            for r in self.results
            if r["action"] == "BUY"
        )

        sell_signals = sum(
            1
            for r in self.results
            if r["action"] == "SELL"
        )

        no_trade = sum(
            1
            for r in self.results
            if r["action"] == "NO_TRADE"
        )

        average_score = (
            sum(
                r["score"]
                for r in self.results
            )
            / total
            if total
            else 0
        )

        average_probability = (
            sum(
                r["probability"]
                for r in self.results
            )
            / total
            if total
            else 0
        )

        return {
            "total": total,
            "approved": approved,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "no_trade": no_trade,
            "average_score": round(
                average_score,
                2,
            ),
            "average_probability": round(
                average_probability,
                2,
            ),
        }


    def show(self):

        metrics = self.calculate()

        print("==============================")
        print("ARMS AI STRATEGY METRICS")
        print("==============================")

        for key, value in metrics.items():
            print(
                f"{key}: {value}"
            )
