from backend.models.backtest_statistics import BacktestStatistics


class StatisticsEngine:
    """
    Calcula métricas básicas de rendimiento a partir
    de una secuencia de resultados monetarios.
    """

    def calculate(
        self,
        pnls: list[float],
    ) -> BacktestStatistics:
        total_trades = len(pnls)

        winning_trades = sum(
            1
            for pnl in pnls
            if pnl > 0
        )

        losing_trades = sum(
            1
            for pnl in pnls
            if pnl < 0
        )

        breakeven_trades = sum(
            1
            for pnl in pnls
            if pnl == 0
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

        net_profit = sum(pnls)

        win_rate = (
            winning_trades
            / total_trades
            * 100
            if total_trades > 0
            else 0.0
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        expectancy = (
            net_profit / total_trades
            if total_trades > 0
            else 0.0
        )

        max_drawdown = self._calculate_max_drawdown(
            pnls
        )

        return BacktestStatistics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            breakeven_trades=breakeven_trades,
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            net_profit=round(net_profit, 2),
            win_rate=round(win_rate, 2),
            profit_factor=(
                round(profit_factor, 4)
                if profit_factor is not None
                else None
            ),
            expectancy=round(expectancy, 2),
            max_drawdown=round(max_drawdown, 2),
        )

    def _calculate_max_drawdown(
        self,
        pnls: list[float],
    ) -> float:
        equity = 0.0
        equity_peak = 0.0
        max_drawdown = 0.0

        for pnl in pnls:
            equity += pnl

            if equity > equity_peak:
                equity_peak = equity

            drawdown = equity_peak - equity

            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown
