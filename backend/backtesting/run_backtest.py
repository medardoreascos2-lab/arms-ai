import sys
from pathlib import Path

from backend.backtesting.backtest_engine import BacktestEngine
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
            "<archivo.csv>"
        )

    file_path = Path(arguments[0])

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {file_path}"
        )

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
    )

    result = engine.run_from_csv(
        file_path=file_path,
    )

    result.show()


if __name__ == "__main__":
    main()
