from __future__ import annotations


class BacktestingMetricsProviderV2:
    """
    Provider que mantiene operaciones de backtesting
    y expone métricas calculadas.
    """


    def __init__(
        self,
        *,
        engine,
    ):

        if not callable(
            getattr(
                engine,
                "calculate",
                None,
            )
        ):
            raise TypeError(
                "engine debe implementar calculate()."
            )

        self._engine = engine

        self._trades = []


    def add_trade(
        self,
        trade,
    ):

        if not isinstance(
            trade,
            dict,
        ):
            raise TypeError(
                "trade debe ser un dict."
            )

        self._trades.append(
            trade
        )


    def get_trades(
        self,
    ):

        return list(
            self._trades
        )


    def get_metrics(
        self,
    ):

        return self._engine.calculate(
            self._trades
        )
