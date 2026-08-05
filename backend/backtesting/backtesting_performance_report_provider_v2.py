from __future__ import annotations


class BacktestingPerformanceReportProviderV2:
    """
    Provider que conecta métricas de backtesting
    con el generador de reportes.
    """


    def __init__(
        self,
        *,
        metrics_provider,
        report_engine,
    ):

        if not callable(
            getattr(
                metrics_provider,
                "get_metrics",
                None,
            )
        ):
            raise TypeError(
                "metrics_provider debe implementar get_metrics()."
            )


        if not callable(
            getattr(
                report_engine,
                "generate",
                None,
            )
        ):
            raise TypeError(
                "report_engine debe implementar generate()."
            )


        self._metrics_provider = (
            metrics_provider
        )

        self._report_engine = (
            report_engine
        )


    def get_report(
        self,
    ):

        metrics = (
            self._metrics_provider
            .get_metrics()
        )

        return (
            self._report_engine
            .generate(
                metrics
            )
        )
