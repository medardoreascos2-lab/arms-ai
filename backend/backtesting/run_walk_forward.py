from pathlib import Path
import sys
from typing import Any

from backend.backtesting.backtest_engine import BacktestEngine
from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)
from backend.backtesting.walk_forward_csv_exporter import (
    WalkForwardCsvExporter,
)
from backend.backtesting.walk_forward_dashboard_exporter import (
    WalkForwardDashboardExporter,
)
from backend.backtesting.walk_forward_engine import (
    WalkForwardEngine,
)
from backend.backtesting.walk_forward_json_exporter import (
    WalkForwardJsonExporter,
)
from backend.backtesting.walk_forward_runner import (
    WalkForwardRunner,
)
from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)
from backend.config_settings import ArmsSettings
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.pipeline.pipeline_mode import PipelineMode


class WalkForwardBacktestAdapter:
    """
    Adapta BacktestEngine a la interfaz esperada
    por WalkForwardEngine.
    """

    def __init__(
        self,
        backtest_engine: BacktestEngine,
    ) -> None:
        self.backtest_engine = backtest_engine

    def run_walk_forward_window(
        self,
        training_candles: list[Any],
        testing_candles: list[Any],
    ):
        # Por ahora usamos el tramo de prueba como evaluación
        # fuera de muestra. El tramo de entrenamiento queda
        # disponible para la futura optimización de parámetros.
        del training_candles

        return self.backtest_engine.run(
            candles=testing_candles,
        )


def build_runner(
    settings: ArmsSettings,
    training_size: int,
    testing_size: int,
    step_size: int,
) -> WalkForwardRunner:
    splitter = WalkForwardSplitter(
        training_size=training_size,
        testing_size=testing_size,
        step_size=step_size,
    )

    minimum_candles = max(
        settings.ema_period,
        settings.rsi_period + 1,
        settings.atr_period + 1,
    )

    def engine_factory(window):
        del window

        pipeline = PipelineFactory(
            settings=settings,
            collector=None,
        ).create(
            mode=PipelineMode.BACKTEST,
        )

        backtest_engine = BacktestEngine(
            pipeline=pipeline,
            minimum_candles=minimum_candles,
            initial_balance=settings.account_balance,
        )

        return WalkForwardBacktestAdapter(
            backtest_engine=backtest_engine,
        )

    walk_forward_engine = WalkForwardEngine(
        splitter=splitter,
        engine_factory=engine_factory,
    )

    return WalkForwardRunner(
        historical_data_loader=HistoricalDataLoader(),
        walk_forward_engine=walk_forward_engine,
    )


def _read_option(
    arguments: list[str],
    option: str,
    default: str,
) -> Path:
    if option not in arguments:
        return Path(default)

    index = arguments.index(option)

    try:
        return Path(arguments[index + 1])
    except IndexError as error:
        raise SystemExit(
            f"Falta el valor de {option}."
        ) from error


def _read_int_option(
    arguments: list[str],
    option: str,
    default: int,
) -> int:
    if option not in arguments:
        return default

    index = arguments.index(option)

    try:
        value = int(arguments[index + 1])
    except IndexError as error:
        raise SystemExit(
            f"Falta el valor de {option}."
        ) from error
    except ValueError as error:
        raise SystemExit(
            f"{option} debe ser un número entero."
        ) from error

    if value <= 0:
        raise SystemExit(
            f"{option} debe ser mayor que cero."
        )

    return value


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
            "Uso: py -m backend.backtesting.run_walk_forward "
            "<archivo.csv> "
            "[--training-size número] "
            "[--testing-size número] "
            "[--step-size número] "
            "[--windows archivo.csv] "
            "[--summary archivo.csv] "
            "[--json archivo.json] "
            "[--dashboard archivo.html]"
        )

    file_path = Path(arguments[0])

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {file_path}"
        )

    training_size = _read_int_option(
        arguments=arguments,
        option="--training-size",
        default=100,
    )
    testing_size = _read_int_option(
        arguments=arguments,
        option="--testing-size",
        default=50,
    )
    step_size = _read_int_option(
        arguments=arguments,
        option="--step-size",
        default=50,
    )

    windows_path = _read_option(
        arguments=arguments,
        option="--windows",
        default=(
            "data/reports/"
            "walk_forward_windows.csv"
        ),
    )
    summary_path = _read_option(
        arguments=arguments,
        option="--summary",
        default=(
            "data/reports/"
            "walk_forward_summary.csv"
        ),
    )
    json_path = _read_option(
        arguments=arguments,
        option="--json",
        default="data/reports/walk_forward.json",
    )
    dashboard_path = _read_option(
        arguments=arguments,
        option="--dashboard",
        default=(
            "data/reports/"
            "walk_forward_dashboard.html"
        ),
    )

    settings = ArmsSettings()

    runner = build_runner(
        settings=settings,
        training_size=training_size,
        testing_size=testing_size,
        step_size=step_size,
    )

    report = runner.run_from_csv(
        file_path=file_path,
    )

    print("------ WALK FORWARD RESULT ------")
    print(f"Ventanas totales: {report.total_windows}")
    print(
        "Ventanas rentables: "
        f"{report.profitable_windows}"
    )
    print(
        "Ventanas perdedoras: "
        f"{report.losing_windows}"
    )
    print(
        "Ventanas en equilibrio: "
        f"{report.breakeven_windows}"
    )
    print(
        "Beneficio neto total: "
        f"${report.total_net_profit:.2f}"
    )
    print(
        "Promedio por ventana: "
        f"${report.average_net_profit:.2f}"
    )
    print(
        "Tasa de ventanas rentables: "
        f"{report.profitable_window_rate:.2f}%"
    )
    print(
        "Stability score: "
        f"{report.stability_score:.2f}"
    )

    WalkForwardCsvExporter().export_csv(
        report=report,
        file_path=windows_path,
        summary_path=summary_path,
    )

    WalkForwardJsonExporter().export_json(
        report=report,
        file_path=json_path,
    )

    WalkForwardDashboardExporter().export_html(
        report=report,
        file_path=dashboard_path,
    )


if __name__ == "__main__":
    main()
