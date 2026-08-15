class StrategyLearningEngineV1:
    """
    Aprende del historial de rendimiento
    de estrategias ARMS AI.
    """


    def __init__(self):

        self.history = []


    def record_result(
        self,
        strategy: str,
        result: str,
        pnl: float,
    ):

        self.history.append(
            {
                "strategy": strategy,
                "result": result,
                "pnl": pnl,
            }
        )


    def analyze_strategy(
        self,
        strategy: str,
    ):

        trades = [
            item
            for item in self.history
            if item["strategy"] == strategy
        ]


        total = len(trades)


        wins = sum(
            1
            for trade in trades
            if trade["result"] == "WIN"
        )


        losses = sum(
            1
            for trade in trades
            if trade["result"] == "LOSS"
        )


        total_pnl = sum(
            trade["pnl"]
            for trade in trades
        )


        win_rate = (
            wins / total * 100
            if total
            else 0
        )


        learning_score = (
            win_rate * 0.6
            +
            (total_pnl / 100)
            * 0.4
        )


        return {
            "strategy": strategy,
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2,
            ),
            "total_pnl": round(
                total_pnl,
                2,
            ),
            "learning_score": round(
                learning_score,
                2,
            ),
        }


    def best_learned_strategy(self):

        strategies = list(
            set(
                item["strategy"]
                for item in self.history
            )
        )


        if not strategies:
            return None


        results = [
            self.analyze_strategy(
                strategy
            )
            for strategy in strategies
        ]


        return max(
            results,
            key=lambda x: x["learning_score"],
        )
