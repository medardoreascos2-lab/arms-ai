from __future__ import annotations


class BacktestingMetricsEngineV2:
    """
    Motor de métricas para resultados
    de backtesting.
    """

    def calculate(
        self,
        trades,
    ):

        if not trades:

            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "net_profit": 0.0,
                "max_drawdown": 0.0,
            }


        pnls = []

        for trade in trades:

            if "pnl" not in trade:

                raise ValueError(
                    "trade debe contener pnl."
                )

            pnls.append(
                float(
                    trade["pnl"]
                )
            )


        total_trades = len(
            pnls
        )

        winning_trades = len(
            [
                pnl
                for pnl in pnls
                if pnl > 0
            ]
        )

        losing_trades = len(
            [
                pnl
                for pnl in pnls
                if pnl < 0
            ]
        )


        win_rate = (
            winning_trades
            / total_trades
            * 100
        )


        gross_profit = sum(
            pnl
            for pnl in pnls
            if pnl > 0
        )

        gross_loss = abs(
            sum(
                pnl
                for pnl in pnls
                if pnl < 0
            )
        )


        profit_factor = (
            round(
                gross_profit / gross_loss,
                10,
            )
            if gross_loss > 0
            else 0.0
        )


        net_profit = sum(
            pnls
        )


        max_drawdown = (
            self._calculate_drawdown(
                pnls
            )
        )


        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "net_profit": net_profit,
            "max_drawdown": max_drawdown,
        }


    def _calculate_drawdown(
        self,
        pnls,
    ):

        balance = 0.0
        peak = 0.0
        max_drawdown = 0.0


        for pnl in pnls:

            balance += pnl

            if balance > peak:
                peak = balance

            drawdown = (
                balance - peak
            )

            if drawdown < max_drawdown:
                max_drawdown = drawdown


        return max_drawdown
