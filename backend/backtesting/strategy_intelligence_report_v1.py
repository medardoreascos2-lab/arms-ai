class StrategyIntelligenceReportV1:
    """
    Reporte ejecutivo de inteligencia
    de estrategia ARMS AI.
    """

    def __init__(
        self,
        certification,
        metrics,
        performance,
    ):
        self.certification = certification
        self.metrics = metrics
        self.performance = performance


    def show(self):

        print(
            "================================"
        )

        print(
            "ARMS AI STRATEGY INTELLIGENCE REPORT"
        )

        print(
            "================================"
        )


        print()
        print("CERTIFICATION")
        print("--------------------------------")

        certification = (
            self.certification.summary()
        )

        print(
            "Tests:",
            certification["total"]
        )

        print(
            "Passed:",
            certification["passed"]
        )

        print(
            "Failed:",
            certification["failed"]
        )

        print(
            "Status:",
            (
                "CERTIFIED"
                if certification["certified"]
                else "REJECTED"
            )
        )


        print()
        print("STRATEGY METRICS")
        print("--------------------------------")

        metrics = (
            self.metrics.calculate()
        )

        for key, value in metrics.items():
            print(
                f"{key}: {value}"
            )


        print()
        print("PERFORMANCE")
        print("--------------------------------")

        performance = (
            self.performance.calculate()
        )

        for key, value in performance.items():
            print(
                f"{key}: {value}"
            )


        print()
        print("================================")
