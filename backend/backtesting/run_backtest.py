from pathlib import Path
import sys

from backend.backtesting.backtest_engine import BacktestEngine
from backend.backtesting.backtest_summary_exporter import (
    BacktestSummaryExporter,
)
from backend.backtesting.equity_curve_exporter import (
    EquityCurveExporter,
)
from backend.backtesting.trade_journal_exporter import (
    TradeJournalExporter,
)
from backend.config_settings import ArmsSettings
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.pipeline.pipeline_mode import PipelineMode


def main(
    args: list[str] | None = None,
) -> None:
    arguments = (
        list(args)
        if args is not None
        else sys.argv[1:]
    )

    if not arguments:
        raise SystemExit(
            "Uso: py -m backend.backtesting.run_backtest "
            "<archivo.csv> "
            "[--journal archivo.csv] "
            "[--equity archivo.csv] "
            "[--summary archivo.json]"
        )

    file_path = Path(arguments[0])

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {file_path}"
        )

    journal_path = Path(
        "data/reports/trade_journal.csv"
    )
    equity_path = Path(
        "data/reports/equity_curve.csv"
    )
    summary_path = Path(
        "data/reports/backtest_summary.json"
    )

    if "--journal" in arguments:
        index = arguments.index("--journal")

        try:
            journal_path = Path(
                arguments[index + 1]
            )
        except IndexError as error:
            raise SystemExit(
                "Falta la ruta del journal."
            ) from error

    if "--equity" in arguments:
        index = arguments.index("--equity")

        try:
            equity_path = Path(
                arguments[index + 1]
            )
        except IndexError as error:
            raise SystemExit(
                "Falta la ruta de la curva de equity."
            ) from error

    if "--summary" in arguments:
        index = arguments.index("--summary")

        try:
            summary_path = Path(
                arguments[index + 1]
            )
        except IndexError as error:
            raise SystemExit(
                "Falta la ruta del resumen."
            ) from error

    settings = ArmsSettings()

    pipeline = PipelineFactory(
        settings=settings,
        collector=None,
    ).create(
        mode=PipelineMode.BACKTEST,
    )

    minimum_candles = max(
        settings.ema_period,
        settings.rsi_period + 1,
        settings.atr_period + 1,
    )

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=minimum_candles,
        initial_balance=settings.account_balance,
    )

    result = engine.run_from_csv(
        file_path=file_path,
    )

    result.show()

    TradeJournalExporter().export_csv(
        trades=result.trades,
        file_path=journal_path,
    )

    EquityCurveExporter().export_csv(
        equity_curve=result.equity_curve,
        file_path=equity_path,
    )

    BacktestSummaryExporter().export_json(
        result=result,
        file_path=summary_path,
        source_file=file_path,
        journal_path=journal_path,
        equity_path=equity_path,
    )


if __name__ == "__main__":
    main()
