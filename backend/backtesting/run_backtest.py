from pathlib import Path
import sys

from backend.backtesting.backtest_engine import BacktestEngine
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
            "<archivo.csv> [--journal archivo.csv]"
        )

    file_path = Path(arguments[0])

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {file_path}"
        )

    journal_path = Path(
        "data/reports/trade_journal.csv"
    )

    if "--journal" in arguments:
        index = arguments.index("--journal")

        try:
            journal_path = Path(
                arguments[index + 1]
            )
        except IndexError:
            raise SystemExit(
                "Falta la ruta del journal."
            )

    settings = ArmsSettings()

    pipeline = PipelineFactory(
        settings=settings,
        collector=None,
    ).create(
        mode=PipelineMode.BACKTEST,
    )

    engine = BacktestEngine(
        pipeline=pipeline,
        minimum_candles=50,
    )

    result = engine.run_from_csv(
        file_path=file_path,
    )

    result.show()

    TradeJournalExporter().export_csv(
        trades=result.trades,
        file_path=journal_path,
    )


if __name__ == "__main__":
    main()