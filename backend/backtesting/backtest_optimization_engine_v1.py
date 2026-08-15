class BacktestOptimizationEngineV1:
    """
    Optimiza configuraciones de estrategia
    usando resultados de backtesting ARMS AI.
    """


    def __init__(self):
        self.configurations = []


    def add_configuration(
        self,
        name: str,
        trades: int,
        wins: int,
        average_rr: float,
        profit_factor: float,
    ):

        win_rate = (
            wins / trades * 100
            if trades
            else 0
        )


        score = (
            (win_rate * 0.4)
            +
            (average_rr * 20 * 0.4)
            +
            (profit_factor * 10 * 0.2)
        )


        self.configurations.append(
            {
                "name": name,
                "trades": trades,
                "wins": wins,
                "win_rate": round(
                    win_rate,
                    2,
                ),
                "average_rr": average_rr,
                "profit_factor": profit_factor,
                "score": round(
                    score,
                    2,
                ),
            }
        )


    def rank(self):

        return sorted(
            self.configurations,
            key=lambda x: x["score"],
            reverse=True,
        )


    def best_configuration(self):

        ranked = self.rank()

        if not ranked:
            return None

        return ranked[0]


    def show(self):

        print("==============================")
        print("ARMS AI OPTIMIZATION REPORT")
        print("==============================")


        for config in self.rank():

            print(
                config
            )
