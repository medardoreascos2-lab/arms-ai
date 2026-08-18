from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from backend.models.candle import Candle

from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


@dataclass(slots=True)
class BacktestPipelineResultV2:
    """
    Resultado de ejecutar y exportar
    un pipeline completo de backtesting.
    """

    candles_processed: int
    report: BacktestReportV2
    json_path: Path
    html_path: Path

    def __post_init__(self) -> None:

        normalized_candles_processed = int(
            self.candles_processed
        )

        if normalized_candles_processed < 0:
            raise ValueError(
                "candles_processed no puede ser negativo."
            )

        if not isinstance(
            self.report,
            BacktestReportV2,
        ):
            raise TypeError(
                "report debe ser BacktestReportV2."
            )

        self.candles_processed = (
            normalized_candles_processed
        )

        self.json_path = Path(
            self.json_path
        )

        self.html_path = Path(
            self.html_path
        )


class BacktestPipelineV2:
    """
    Orquesta la ejecución de una sesión de backtesting,
    la construcción del reporte y su exportación.
    """

    def __init__(
        self,
        *,
        backtest_session_v2,
        json_exporter_v2,
        html_exporter_v2,
    ) -> None:

        if not callable(
            getattr(
                backtest_session_v2,
                "run",
                None,
            )
        ):
            raise TypeError(
                "backtest_session_v2 debe implementar run()."
            )

        if not callable(
            getattr(
                backtest_session_v2,
                "build_report",
                None,
            )
        ):
            raise TypeError(
                "backtest_session_v2 debe implementar "
                "build_report()."
            )

        if not callable(
            getattr(
                json_exporter_v2,
                "export",
                None,
            )
        ):
            raise TypeError(
                "json_exporter_v2 debe implementar export()."
            )

        if not callable(
            getattr(
                html_exporter_v2,
                "export",
                None,
            )
        ):
            raise TypeError(
                "html_exporter_v2 debe implementar export()."
            )

        self.backtest_session_v2 = (
            backtest_session_v2
        )

        self.json_exporter_v2 = (
            json_exporter_v2
        )

        self.html_exporter_v2 = (
            html_exporter_v2
        )

    def run(
        self,
        *,
        output_directory,
        json_filename: str = "backtest.json",
        html_filename: str = "backtest.html",
        candles=None,
    ) -> BacktestPipelineResultV2:

        normalized_json_filename = str(
            json_filename
        ).strip()

        normalized_html_filename = str(
            html_filename
        ).strip()

        if not normalized_json_filename:
            raise ValueError(
                "json_filename no puede estar vacío."
            )

        if not normalized_html_filename:
            raise ValueError(
                "html_filename no puede estar vacío."
            )

        normalized_output_directory = Path(
            output_directory
        )

        if candles is not None:

            if not isinstance(
                candles,
                list,
            ):
                candles = list(
                    candles
                )

            normalized_candles = [
                self._normalize_candle(
                    candle
                )
                for candle in candles
            ]

            self.backtest_session_v2.backtest_runner_v2.replay_engine_v2.load(
                normalized_candles
            )


        candles_processed = int(
            self.backtest_session_v2.run()
        )

        if candles_processed < 0:
            raise ValueError(
                "run() no puede devolver una cantidad "
                "negativa de velas."
            )

        report = (
            self.backtest_session_v2.build_report(
                candles_processed=candles_processed,
            )
        )

        if not isinstance(
            report,
            BacktestReportV2,
        ):
            raise TypeError(
                "build_report() debe devolver "
                "BacktestReportV2."
            )

        json_output_path = (
            normalized_output_directory
            / normalized_json_filename
        )

        html_output_path = (
            normalized_output_directory
            / normalized_html_filename
        )

        json_path = self.json_exporter_v2.export(
            report=report,
            output_path=json_output_path,
        )

        html_path = self.html_exporter_v2.export(
            report=report,
            output_path=html_output_path,
        )

        return BacktestPipelineResultV2(
            candles_processed=candles_processed,
            report=report,
            json_path=Path(json_path),
            html_path=Path(html_path),
        )

    @staticmethod
    def _normalize_candle(
        candle,
    ) -> Candle:

        if isinstance(
            candle,
            Candle,
        ):
            return candle


        if not isinstance(
            candle,
            dict,
        ):
            raise TypeError(
                "Cada candle debe ser dict o Candle."
            )


        timestamp = candle.get(
            "timestamp"
        )


        if isinstance(
            timestamp,
            str,
        ):
            timestamp = datetime.fromisoformat(
                timestamp
            )


        if timestamp is None:
            timestamp = datetime.now()


        return Candle(
            symbol=str(
                candle.get(
                    "symbol",
                    "NQ",
                )
            ),
            timeframe=str(
                candle.get(
                    "timeframe",
                    "1m",
                )
            ),
            open=float(
                candle["open"]
            ),
            high=float(
                candle["high"]
            ),
            low=float(
                candle["low"]
            ),
            close=float(
                candle["close"]
            ),
            volume=float(
                candle.get(
                    "volume",
                    0,
                )
            ),
            timestamp=timestamp,
        )
