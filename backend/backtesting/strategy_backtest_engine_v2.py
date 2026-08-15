class StrategyBacktestEngineV2:
    """
    Motor avanzado de backtesting
    de estrategias ARMS AI.
    """

    def __init__(self):
        self.trades = []


    def add_trade(
        self,
        trade: dict,
    ):
        self.trades.append(
            trade
        )


    def calculate_metrics(self):

        total = len(
            self.trades
        )

        wins = [
            t for t in self.trades
            if t.get("pnl", 0) > 0
        ]

        losses = [
            t for t in self.trades
            if t.get("pnl", 0) <= 0
        ]

        win_rate = (
            len(wins) / total * 100
            if total
            else 0
        )

        gross_profit = sum(
            t["pnl"]
            for t in wins
        )

        gross_loss = abs(
            sum(
                t["pnl"]
                for t in losses
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss
            else 0
        )

        average_rr = (
            sum(
                t.get("rr", 0)
                for t in self.trades
            )
            / total
            if total
            else 0
        )

        return {
            "trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(
                win_rate,
                2,
            ),
            "profit_factor": round(
                profit_factor,
                2,
            ),
            "average_rr": round(
                average_rr,
                2,
            ),
        }


    def show(self):

        print(
            "=============================="
        )

        print(
            "ARMS AI BACKTEST PERFORMANCE"
        )

        print(
            "=============================="
        )

        for key, value in (
            self.calculate_metrics()
            .items()
        ):
            print(
                f"{key}: {value}"
            )
