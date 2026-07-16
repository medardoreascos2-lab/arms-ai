from pathlib import Path
import sys
from typing import Any

from backend.backtesting.backtest_engine import BacktestEngine
from backend.backtesting.historical_data_loader import (
    HistoricalDataLoader,
)
from backend.backtesting.parameter_evaluator import (
    ParameterEvaluator,
)
from backend.backtesting.parameter_grid import (
    ParameterGrid,
)
from backend.backtesting.walk_forward_optimization_csv_exporter import (
    WalkForwardOptimizationCsvExporter,
)
from backend.backtesting.walk_forward_optimization_dashboard_exporter import (
    WalkForwardOptimizationDashboardExporter,
)
from backend.backtesting.walk_forward_optimization_json_exporter import (
    WalkForwardOptimizationJsonExporter,
)
from backend.backtesting.walk_forward_optimization_runner import (
    WalkForwardOptimizationRunner,
)
from backend.backtesting.walk_forward_optimizer import (
    WalkForwardOptimizer,
)
from backend.backtesting.walk_forward_parameter_selector import (
    WalkForwardParameterSelector,
)
from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)
from backend.config_settings import ArmsSettings
from backend.pipeline.pipeline_factory import PipelineFactory
from backend.pipeline.pipeline_mode import PipelineMode


def _read_path_option(
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


def _build_parameter_grid(
    settings: ArmsSettings,
) -> ParameterGrid:
    return ParameterGrid(
        {
            "ema_period": [
                max(2, settings.ema_period // 2),
                settings.ema_period,
                settings.ema_period * 2,
            ],
            "rsi_period": [
                max(2, settings.rsi_period - 4),
                settings.rsi_period,
                settings.rsi_period + 7,
            ],
            "atr_period": [
                max(2, settings.atr_period - 4),
                settings.atr_period,
                settings.atr_period + 6,
            ],
            "risk_percent": [
                max(0.1, settings.risk_percent / 2),
                settings.risk_percent,
                min(100.0, settings.risk_percent * 1.5),
            ],
        }
    )


def _build_backtest_engine(
    settings: ArmsSettings,
) -> BacktestEngine:
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

    return BacktestEngine(
        pipeline=pipeline,
        minimum_candles=minimum_candles,
        initial_balance=settings.account_balance,
    )


def build_runner(
    settings: ArmsSettings,
    training_size: int,
    testing_size: int,
    step_size: int,
) -> WalkForwardOptimizationRunner:
    splitter = WalkForwardSplitter(
        training_size=training_size,
        testing_size=testing_size,
        step_size=step_size,
    )

    parameter_grid = _build_parameter_grid(
        settings
    )

    def engine_factory(
        parameters: dict[str, Any],
    ) -> BacktestEngine:
        candidate_settings = ArmsSettings(
            **{
                **settings.__dict__,
                **parameters,
            }
        )

        return _build_backtest_engine(
            candidate_settings
        )

    evaluator = ParameterEvaluator(
        engine_factory=engine_factory,
    )

    selector = WalkForwardParameterSelector(
        metric="net_profit",
        maximize=True,
    )

    optimizer = WalkForwardOptimizer(
        parameter_grid=parameter_grid,
        evaluator=evaluator,
        selector=selector,
    )

    return WalkForwardOptimizationRunner(
        splitter=splitter,
        optimizer=optimizer,
    )


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
            "Uso: py -m "
            "backend.backtesting.run_walk_forward_optimization "
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
        default=100,
    )
    step_size = _read_int_option(
        arguments=arguments,
        option="--step-size",
        default=50,
    )

    windows_path = _read_path_option(
        arguments=arguments,
        option="--windows",
        default=(
            "data/reports/"
            "walk_forward_optimization_windows.csv"
        ),
    )
    summary_path = _read_path_option(
        arguments=arguments,
        option="--summary",
        default=(
            "data/reports/"
            "walk_forward_optimization_summary.csv"
        ),
    )
    json_path = _read_path_option(
        arguments=arguments,
        option="--json",
        default=(
            "data/reports/"
            "walk_forward_optimization.json"
        ),
    )
    dashboard_path = _read_path_option(
        arguments=arguments,
        option="--dashboard",
        default=(
            "data/reports/"
            "walk_forward_optimization_dashboard.html"
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

    print(
        "------ WALK FORWARD OPTIMIZATION RESULT ------"
    )
    print(
        f"Ventanas totales: {report.total_windows}"
    )
    print(
        "Ventanas rentables en testing: "
        f"{report.profitable_testing_windows}"
    )
    print(
        "Ventanas perdedoras en testing: "
        f"{report.losing_testing_windows}"
    )
    print(
        "Beneficio neto training: "
        f"${report.total_training_net_profit:.2f}"
    )
    print(
        "Beneficio neto testing: "
        f"${report.total_testing_net_profit:.2f}"
    )
    print(
        "Tasa rentable testing: "
        f"{report.testing_profitable_rate:.2f}%"
    )
    print(
        "Ventanas con posible overfit: "
        f"{report.overfit_windows}"
    )
    print(
        "Overfit rate: "
        f"{report.overfit_rate:.2f}%"
    )

    WalkForwardOptimizationCsvExporter().export_csv(
        report=report,
        file_path=windows_path,
        summary_path=summary_path,
    )

    WalkForwardOptimizationJsonExporter().export_json(
        report=report,
        file_path=json_path,
    )

    WalkForwardOptimizationDashboardExporter().export_html(
        report=report,
        file_path=dashboard_path,
    )


if __name__ == "__main__":
    main()
