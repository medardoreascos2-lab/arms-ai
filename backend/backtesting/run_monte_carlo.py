import csv
from pathlib import Path
import sys

from backend.backtesting.monte_carlo_csv_exporter import (
    MonteCarloCsvExporter,
)
from backend.backtesting.monte_carlo_dashboard_exporter import (
    MonteCarloDashboardExporter,
)
from backend.backtesting.monte_carlo_engine import (
    MonteCarloEngine,
)
from backend.backtesting.monte_carlo_json_exporter import (
    MonteCarloJsonExporter,
)
from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)
from backend.config_settings import ArmsSettings


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


def _read_float_option(
    arguments: list[str],
    option: str,
    default: float,
) -> float:
    if option not in arguments:
        return default

    index = arguments.index(option)

    try:
        value = float(arguments[index + 1])
    except IndexError as error:
        raise SystemExit(
            f"Falta el valor de {option}."
        ) from error
    except ValueError as error:
        raise SystemExit(
            f"{option} debe ser un número."
        ) from error

    if value <= 0:
        raise SystemExit(
            f"{option} debe ser mayor que cero."
        )

    return value


def _read_method(
    arguments: list[str],
) -> str:
    option = "--method"

    if option not in arguments:
        return "shuffle"

    index = arguments.index(option)

    try:
        value = arguments[index + 1]
    except IndexError as error:
        raise SystemExit(
            "Falta el valor de --method."
        ) from error

    if value not in {
        "shuffle",
        "bootstrap",
    }:
        raise SystemExit(
            "--method debe ser 'shuffle' o 'bootstrap'."
        )

    return value


def _read_optional_seed(
    arguments: list[str],
) -> int | None:
    option = "--seed"

    if option not in arguments:
        return None

    index = arguments.index(option)

    try:
        return int(arguments[index + 1])
    except IndexError as error:
        raise SystemExit(
            "Falta el valor de --seed."
        ) from error
    except ValueError as error:
        raise SystemExit(
            "--seed debe ser un número entero."
        ) from error


def _load_pnls(
    file_path: str | Path,
) -> list[float]:
    path = Path(file_path)

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        fieldnames = set(
            reader.fieldnames or []
        )

        if "pnl" not in fieldnames:
            raise ValueError(
                "El archivo requiere la columna 'pnl'."
            )

        pnls: list[float] = []

        for line_number, row in enumerate(
            reader,
            start=2,
        ):
            try:
                pnls.append(
                    float(row["pnl"])
                )
            except (
                TypeError,
                ValueError,
                KeyError,
            ) as error:
                raise ValueError(
                    "Valor pnl inválido en la línea "
                    f"{line_number}: {error}"
                ) from error

    if not pnls:
        raise ValueError(
            "El archivo no contiene valores pnl."
        )

    return pnls


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
            "Uso: py -m backend.backtesting.run_monte_carlo "
            "<trade_journal.csv> "
            "[--simulations número] "
            "[--initial-balance número] "
            "[--ruin-balance número] "
            "[--seed número] "
            "[--method shuffle|bootstrap] "
            "[--json archivo.json] "
            "[--csv archivo.csv] "
            "[--dashboard archivo.html]"
        )

    file_path = Path(arguments[0])

    if not file_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {file_path}"
        )

    settings = ArmsSettings()

    simulations = _read_int_option(
        arguments=arguments,
        option="--simulations",
        default=1000,
    )

    initial_balance = _read_float_option(
        arguments=arguments,
        option="--initial-balance",
        default=float(settings.account_balance),
    )

    ruin_balance = _read_float_option(
        arguments=arguments,
        option="--ruin-balance",
        default=initial_balance * 0.5,
    )

    seed = _read_optional_seed(
        arguments
    )

    method = _read_method(
        arguments
    )

    json_path = _read_path_option(
        arguments=arguments,
        option="--json",
        default="data/reports/monte_carlo.json",
    )

    csv_path = _read_path_option(
        arguments=arguments,
        option="--csv",
        default=(
            "data/reports/"
            "monte_carlo_summary.csv"
        ),
    )

    dashboard_path = _read_path_option(
        arguments=arguments,
        option="--dashboard",
        default=(
            "data/reports/"
            "monte_carlo_dashboard.html"
        ),
    )

    pnls = _load_pnls(
        file_path=file_path,
    )

    result = MonteCarloEngine(
        simulations=simulations,
        seed=seed,
        method=method,
    ).run(
        pnls=pnls,
        initial_balance=initial_balance,
    )

    report = MonteCarloReport.from_result(
        result=result,
        ruin_balance=ruin_balance,
    )

    print("------ MONTE CARLO RESULT ------")
    print(f"Método: {method}")
    print(
        f"Simulaciones: {report.total_simulations}"
    )
    print(
        "Balance final promedio: "
        f"${report.average_final_balance:.2f}"
    )
    print(
        "Balance final mediano: "
        f"${report.median_final_balance:.2f}"
    )
    print(
        "Mejor balance final: "
        f"${report.best_final_balance:.2f}"
    )
    print(
        "Peor balance final: "
        f"${report.worst_final_balance:.2f}"
    )
    print(
        "Drawdown máximo promedio: "
        f"${report.average_max_drawdown:.2f}"
    )
    print(
        "Peor drawdown máximo: "
        f"${report.worst_max_drawdown:.2f}"
    )
    print(
        "Probabilidad de pérdida: "
        f"{report.loss_probability:.2f}%"
    )
    print(
        "Probabilidad de ruina: "
        f"{report.ruin_probability:.2f}%"
    )

    MonteCarloJsonExporter().export_json(
        report=report,
        file_path=json_path,
    )

    MonteCarloCsvExporter().export_csv(
        report=report,
        file_path=csv_path,
    )

    MonteCarloDashboardExporter().export_html(
        report=report,
        file_path=dashboard_path,
    )


if __name__ == "__main__":
    main()
