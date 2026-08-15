class StrategyIntelligenceWidgetV1:
    """
    Prepara datos de inteligencia estratégica
    para Dashboard ARMS AI.
    """

    def build(
        self,
        report,
    ) -> dict:

        certification = (
            report.certification.summary()
        )

        metrics = (
            report.metrics.calculate()
        )

        performance = (
            report.performance.calculate()
        )

        return {
            "strategy_status": (
                "CERTIFIED"
                if certification["certified"]
                else "REJECTED"
            ),

            "certification": {
                "tests": certification["total"],
                "passed": certification["passed"],
                "failed": certification["failed"],
            },

            "metrics": {
                "average_score": metrics[
                    "average_score"
                ],
                "average_probability": metrics[
                    "average_probability"
                ],
                "buy_signals": metrics[
                    "buy_signals"
                ],
                "sell_signals": metrics[
                    "sell_signals"
                ],
                "no_trade": metrics[
                    "no_trade"
                ],
            },

            "performance": {
                "trades": performance[
                    "trades"
                ],
                "win_rate": performance[
                    "win_rate"
                ],
                "average_rr": performance[
                    "average_rr"
                ],
            },
        }
