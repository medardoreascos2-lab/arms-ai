from pathlib import Path
from typing import Any, Callable

from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)
from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)


class WalkForwardRunner:
    """
    Coordina la carga de datos, la ejecución walk-forward
    y la construcción del reporte final.
    """

    def __init__(
        self,
        historical_data_loader: Any | None,
        walk_forward_engine: Any,
        report_factory: Callable[
            [Any],
            WalkForwardReport,
        ] | None = None,
    ) -> None:
        if walk_forward_engine is None:
            raise TypeError(
                "walk_forward_engine es obligatorio."
            )

        if report_factory is not None and not callable(
            report_factory
        ):
            raise TypeError(
                "report_factory debe ser callable."
            )

        self.historical_data_loader = (
            historical_data_loader
            or HistoricalDataLoader()
        )
        self.walk_forward_engine = walk_forward_engine
        self.report_factory = (
            report_factory
            or WalkForwardReport.from_result
        )

    def run(
        self,
        candles: list[Any],
    ) -> WalkForwardReport:
        if not candles:
            raise ValueError(
                "WalkForwardRunner requiere candles."
            )

        result = self.walk_forward_engine.run(
            candles=candles,
        )

        return self.report_factory(result)

    def run_from_csv(
        self,
        file_path: str | Path,
    ) -> WalkForwardReport:
        candles = self.historical_data_loader.load_csv(
            file_path=file_path,
        )

        return self.run(
            candles=candles,
        )
