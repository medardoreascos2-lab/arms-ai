from __future__ import annotations


class BacktestingPerformanceReportV2:
    """
    Generador de reportes de rendimiento
    para estrategias de backtesting.
    """


    REQUIRED_FIELDS = {
        "total_trades",
        "winning_trades",
        "losing_trades",
        "win_rate",
        "profit_factor",
        "net_profit",
        "max_drawdown",
    }


    def generate(
        self,
        metrics,
    ):

        if not isinstance(
            metrics,
            dict,
        ):
            raise ValueError(
                "metrics debe ser un dict."
            )


        missing = (
            self.REQUIRED_FIELDS
            -
            set(metrics.keys())
        )


        if missing:

            raise ValueError(
                "metrics incompletas."
            )


        score = self._calculate_score(
            metrics
        )


        rating = (
            "GOOD"
            if score >= 70
            else "WARNING"
            if score >= 40
            else "BAD"
        )


        return {
            "score": score,
            "rating": rating,
            "metrics": metrics,
        }


    def _calculate_score(
        self,
        metrics,
    ):

        score = 0


        if metrics["win_rate"] >= 60:
            score += 30


        if metrics["profit_factor"] >= 2.0:
            score += 30


        if metrics["net_profit"] > 0:
            score += 25


        if metrics["max_drawdown"] > -1000:
            score += 15


        if metrics["total_trades"] < 10:
            score -= 15

        elif metrics["total_trades"] < 30:
            score -= 10


        # Ajuste de certificación:
        # solo aplica cuando existe suficiente muestra

        if metrics["total_trades"] >= 10:
            score -= 15


        return max(
            score,
            0,
        )
