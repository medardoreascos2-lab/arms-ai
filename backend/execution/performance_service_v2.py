
from __future__ import annotations



class PerformanceServiceV2:
    """
    Servicio encargado de conectar
    Trade Journal con Performance Analyzer.
    """



    def __init__(
        self,
        *,
        journal,
        analyzer,
    ):


        if not (
            callable(
                getattr(
                    journal,
                    "get_closed_trades",
                    None,
                )
            )
            or callable(
                getattr(
                    journal,
                    "get_trades",
                    None,
                )
            )
        ):
            raise TypeError(
                "journal debe implementar get_closed_trades() o get_trades()."
            )



        if not callable(
            getattr(
                analyzer,
                "analyze",
                None,
            )
        ):
            raise TypeError(
                "analyzer debe implementar analyze()."
            )



        self.journal = (
            journal
        )


        self.analyzer = (
            analyzer
        )




    def get_performance(
        self,
    ) -> dict:


        if callable(
            getattr(
                self.journal,
                "get_closed_trades",
                None,
            )
        ):

            trades = (
                self.journal
                .get_closed_trades()
            )

        else:

            trades = (
                self.journal
                .get_trades()
            )



        if trades is None:

            return {
                "status": "BLOCKED",
                "reason": "INVALID_HISTORY",
            }



        return self.analyzer.analyze(
            trades=trades,
        )
