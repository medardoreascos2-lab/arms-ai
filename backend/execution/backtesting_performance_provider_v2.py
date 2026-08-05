
from __future__ import annotations



class BacktestingPerformanceProviderV2:
    """
    Proveedor de métricas simuladas
    para resultados de backtesting.
    """



    def get_performance(
        self,
    ) -> dict:


        return {

            "total_trades": 10,

            "winning_trades": 7,

            "losing_trades": 3,

            "win_rate": 70.0,

            "net_profit": 1250,

        }
