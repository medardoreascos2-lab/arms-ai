
from __future__ import annotations



class BacktestingStrategyPerformanceProviderV2:
    """
    Proveedor de rendimiento de estrategias
    basado en resultados simulados de backtesting.
    """


    def get_strategy_performance(
        self,
    ) -> dict:


        return {

            "total_trades": 10,

            "strategies": {

                "STR-001": {

                    "strategy_id": "STR-001",

                    "strategy_name": "EMA50 Smart Money",

                    "win_rate": 70.0,

                    "net_profit": 1500,

                },

                "STR-002": {

                    "strategy_id": "STR-002",

                    "strategy_name": "Breakout",

                    "win_rate": 50.0,

                    "net_profit": 300,

                },

            },

            "best_strategy": {

                "strategy_id": "STR-001",

                "strategy_name": "EMA50 Smart Money",

            },

        }
