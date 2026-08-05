
from __future__ import annotations



class BacktestingStrategyPerformanceProviderV2:
    """
    Provider de rendimiento estratégico
    para Backtesting Dashboard.
    """



    def get_strategy_performance(
        self,
    ) -> dict:


        return {

            "strategies": {

                "STR-001": {

                    "strategy_id": "STR-001",

                    "strategy_name": (
                        "EMA50 Smart Money"
                    ),

                    "win_rate": 70.0,

                    "net_profit": 1500,

                }

            },


            "best_strategy": {

                "strategy_id": "STR-001",

                "strategy_name": (
                    "EMA50 Smart Money"
                ),

            },

        }
