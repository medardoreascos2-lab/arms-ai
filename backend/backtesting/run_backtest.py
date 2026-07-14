import sys
from pathlib import Path

from backend.backtesting.backtest_engine import BacktestEngine
from backend.config_settings import ArmsSettings
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.pipeline.pipeline_mode import PipelineMode
from backend.services.data_collector import DataCollector


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

    collector = DataCollector(
        provider=settings.provider,
    )

    pipeline = PipelineFactory(
        settings=settings,
        collector=collector,
    ).create(
        mode=PipelineMode.SIMULATION,
    )

    engine = BacktestEngine(
        pipeline=pipeline,
    )

    result = engine.run_from_csv(
        file_path=file_path,
    )

    result.show()


if __name__ == "__main__":
    main()
