class BacktestAnalyticsEngineV2:
    """
    Analiza resultados de backtesting
    de ARMS AI.
    """


    def __init__(self):
        self.trades = []
        self.scenarios = []


    def add_trade(
        self,
        scenario: str,
        trade: dict,
    ):

        self.trades.append(
            trade
        )

        self.scenarios.append(
            {
                "scenario": scenario,
                "trade": trade,
            }
        )


    def calculate(self):

        total = len(
            self.trades
        )


        wins = [
            t for t in self.trades
            if t.get("result") == "WIN"
        ]


        losses = [
            t for t in self.trades
            if t.get("result") == "LOSS"
        ]


        buy_trades = [
            t for t in self.trades
            if t.get("direction") == "BUY"
        ]


        sell_trades = [
            t for t in self.trades
            if t.get("direction") == "SELL"
        ]


        win_rate = (
            len(wins) / total * 100
            if total
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
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(
                win_rate,
                2,
            ),
            "average_rr": round(
                average_rr,
                2,
            ),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
        }



    def scenario_report(self):

        report = {}

        for item in self.scenarios:

            name = item["scenario"]

            trade = item["trade"]

            report[name] = {
                "result": trade.get(
                    "result"
                ),
                "direction": trade.get(
                    "direction"
                ),
                "rr": trade.get(
                    "rr"
                ),
                "exit_reason": trade.get(
                    "exit_reason"
                ),
            }


        return report



    def show(self):

        print("==============================")
        print("ARMS AI BACKTEST ANALYTICS")
        print("==============================")


        for key, value in (
            self.calculate()
            .items()
        ):
            print(
                f"{key}: {value}"
            )


        print()
        print("SCENARIOS")
        print("------------------------------")


        for key, value in (
            self.scenario_report()
            .items()
        ):
            print(
                key,
                value
            )
