class StrategyPerformanceTrackerV1:
    """
    Registra resultados de operaciones
    simuladas de ARMS AI.
    """

    def __init__(self):
        self.trades = []


    def add_trade(
        self,
        direction: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        exit_price: float,
    ):

        if direction == "BUY":

            pnl = exit_price - entry

            risk = entry - stop_loss

        elif direction == "SELL":

            pnl = entry - exit_price

            risk = stop_loss - entry

        else:
            return


        rr = (
            pnl / risk
            if risk > 0
            else 0
        )


        self.trades.append(
            {
                "direction": direction,
                "entry": entry,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "exit_price": exit_price,
                "pnl": pnl,
                "rr": rr,
                "win": pnl > 0,
            }
        )


    def calculate(self):

        total = len(self.trades)

        wins = sum(
            1
            for t in self.trades
            if t["win"]
        )

        losses = total - wins


        win_rate = (
            wins / total * 100
            if total
            else 0
        )


        average_rr = (
            sum(
                t["rr"]
                for t in self.trades
            )
            / total
            if total
            else 0
        )


        return {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2,
            ),
            "average_rr": round(
                average_rr,
                2,
            ),
        }


    def show(self):

        result = self.calculate()

        print("==============================")
        print("ARMS AI PERFORMANCE REPORT")
        print("==============================")

        for key, value in result.items():
            print(
                f"{key}: {value}"
            )
