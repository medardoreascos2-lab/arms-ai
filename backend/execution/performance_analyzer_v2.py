
from __future__ import annotations



class PerformanceAnalyzerV2:
    """
    Analizador de rendimiento de operaciones.

    Convierte el historial de trades en métricas
    estadísticas para ARMS AI.
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
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "net_profit": 0,
            }



        winning_trades = 0
        losing_trades = 0
        net_profit = 0



        for trade in trades:


            if "realized_pnl" in trade:

                profit = float(
                    trade.get(
                        "realized_pnl",
                        0,
                    )
                )


                if profit > 0:

                    winning_trades += 1


                elif profit < 0:

                    losing_trades += 1


            else:

                if trade.get(
                    "result"
                ) == "WIN":

                    winning_trades += 1


                elif trade.get(
                    "result"
                ) == "LOSS":

                    losing_trades += 1


                profit = float(
                    trade.get(
                        "profit",
                        0,
                    )
                )


            net_profit += profit



        win_rate = (
            winning_trades
            /
            total_trades
        ) * 100



        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "net_profit": net_profit,
        }
