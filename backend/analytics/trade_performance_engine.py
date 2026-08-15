from dataclasses import dataclass
from typing import List


@dataclass
class PerformanceReport:

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    total_profit: float

    average_trade: float

    best_trade: float

    worst_trade: float



class TradePerformanceEngine:


    def __init__(self):
        pass



    def analyze(

        self,

        trades: List,

    ) -> PerformanceReport:


        total = len(trades)


        if total == 0:

            return PerformanceReport(

                total_trades=0,

                winning_trades=0,

                losing_trades=0,

                win_rate=0,

                total_profit=0,

                average_trade=0,

                best_trade=0,

                worst_trade=0,

            )



        results = []


        for trade in trades:

            result = getattr(
                trade,
                "profit",
                0
            )

            results.append(
                result
            )



        winning = len(
            [
                r for r in results
                if r > 0
            ]
        )


        losing = len(
            [
                r for r in results
                if r < 0
            ]
        )


        total_profit = sum(
            results
        )


        return PerformanceReport(

            total_trades=total,

            winning_trades=winning,

            losing_trades=losing,

            win_rate=round(
                (winning / total) * 100,
                2
            ),

            total_profit=total_profit,

            average_trade=round(
                total_profit / total,
                2
            ),

            best_trade=max(results),

            worst_trade=min(results),

        )
