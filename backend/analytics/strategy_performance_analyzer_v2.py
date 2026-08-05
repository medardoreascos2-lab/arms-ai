
from __future__ import annotations



class StrategyPerformanceAnalyzerV2:
    """
    Analizador encargado de evaluar
    rendimiento individual por estrategia.
    """



    def analyze(
        self,
        *,
        trades: list | None,
    ) -> dict:



        if not isinstance(
            trades,
            list,
        ):

            return {
                "status": "BLOCKED",
                "reason": "INVALID_HISTORY",
            }



        total_trades = len(
            trades
        )



        if total_trades == 0:

            return {
                "total_trades": 0,
                "strategies": {},
                "best_strategy": None,
            }



        strategies = {}



        for trade in trades:


            strategy_id = trade.get(
                "strategy_id"
            )


            strategy_name = trade.get(
                "strategy_name"
            )


            if strategy_id not in strategies:

                strategies[strategy_id] = {

                    "strategy_id": strategy_id,

                    "strategy_name": strategy_name,

                    "total_trades": 0,

                    "winning_trades": 0,

                    "losing_trades": 0,

                    "net_profit": 0,

                }



            strategy = strategies[strategy_id]


            strategy["total_trades"] += 1


            if trade.get(
                "result"
            ) == "WIN":

                strategy["winning_trades"] += 1


            elif trade.get(
                "result"
            ) == "LOSS":

                strategy["losing_trades"] += 1



            strategy["net_profit"] += float(
                trade.get(
                    "profit",
                    0,
                )
            )



        for strategy in strategies.values():


            strategy["win_rate"] = (

                strategy["winning_trades"]

                /

                strategy["total_trades"]

            ) * 100



        best_strategy = max(
            strategies.values(),
            key=lambda item: item["net_profit"],
        )



        return {

            "total_trades": total_trades,

            "strategies": strategies,

            "best_strategy": best_strategy,

        }
