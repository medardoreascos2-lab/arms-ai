from __future__ import annotations

import csv
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import sys

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_csv_exporter import (
    PortfolioCsvExporter,
)
from backend.portfolio.portfolio_dashboard_exporter import (
    PortfolioDashboardExporter,
)
from backend.portfolio.portfolio_json_exporter import (
    PortfolioJsonExporter,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_report import (
    PortfolioReport,
)
from backend.portfolio.portfolio_snapshot import (
    PortfolioSnapshot,
)


REQUIRED_COLUMNS = {
    "timestamp",
    "cash",
    "symbol",
    "quantity",
    "average_price",
    "current_price",
}


def _read_path_option(
    *,
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


def build_report_from_csv(
    *,
    file_path: str | Path,
) -> PortfolioReport:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {path}"
        )

    grouped_rows: OrderedDict[
        datetime,
        dict[str, object],
    ] = OrderedDict()

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        fieldnames = set(
            reader.fieldnames or []
        )

        missing_columns = (
            REQUIRED_COLUMNS - fieldnames
        )

        if missing_columns:
            missing = ", ".join(
                sorted(missing_columns)
            )

            raise ValueError(
                "Faltan columnas requeridas: "
                f"{missing}"
            )

        for line_number, row in enumerate(
            reader,
            start=2,
        ):
            try:
                timestamp = datetime.fromisoformat(
                    row["timestamp"].strip()
                )

                cash = float(
                    row["cash"]
                )
            except (
                TypeError,
                ValueError,
                KeyError,
            ) as error:
                raise ValueError(
                    "Registro inválido en la línea "
                    f"{line_number}: {error}"
                ) from error

            if timestamp not in grouped_rows:
                grouped_rows[timestamp] = {
                    "cash": cash,
                    "positions": [],
                }
            else:
                existing_cash = float(
                    grouped_rows[timestamp]["cash"]
                )

                if existing_cash != cash:
                    raise ValueError(
                        "cash inconsistente para el "
                        f"timestamp {timestamp.isoformat()}."
                    )

            symbol = (
                row.get("symbol") or ""
            ).strip()

            if not symbol:
                continue

            try:
                position = PortfolioPosition(
                    symbol=symbol,
                    quantity=float(
                        row["quantity"]
                    ),
                    average_price=float(
                        row["average_price"]
                    ),
                    current_price=float(
                        row["current_price"]
                    ),
                )
            except (
                TypeError,
                ValueError,
                KeyError,
            ) as error:
                raise ValueError(
                    "Posición inválida en la línea "
                    f"{line_number}: {error}"
                ) from error

            positions = grouped_rows[
                timestamp
            ]["positions"]

            positions.append(position)

    if not grouped_rows:
        raise ValueError(
            "El archivo no contiene snapshots."
        )

    snapshots = [
        PortfolioSnapshot(
            timestamp=timestamp,
            portfolio=Portfolio(
                positions=data["positions"],
            ),
            cash=float(data["cash"]),
        )
        for timestamp, data in grouped_rows.items()
    ]

    return PortfolioReport.from_snapshots(
        snapshots=snapshots,
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
            "Uso: py -m backend.portfolio.run_portfolio "
            "<portfolio.csv> "
            "[--json archivo.json] "
            "[--summary archivo.csv] "
            "[--snapshots archivo.csv] "
            "[--dashboard archivo.html]"
        )

    source_file = Path(
        arguments[0]
    )

    if not source_file.exists():
        raise FileNotFoundError(
            f"No existe el archivo: {source_file}"
        )

    json_path = _read_path_option(
        arguments=arguments,
        option="--json",
        default="data/reports/portfolio.json",
    )

    summary_path = _read_path_option(
        arguments=arguments,
        option="--summary",
        default=(
            "data/reports/"
            "portfolio_summary.csv"
        ),
    )

    snapshots_path = _read_path_option(
        arguments=arguments,
        option="--snapshots",
        default=(
            "data/reports/"
            "portfolio_snapshots.csv"
        ),
    )

    dashboard_path = _read_path_option(
        arguments=arguments,
        option="--dashboard",
        default=(
            "data/reports/"
            "portfolio_dashboard.html"
        ),
    )

    report = build_report_from_csv(
        file_path=source_file,
    )

    print("------ PORTFOLIO RESULT ------")
    print(
        f"Snapshots: {report.total_snapshots}"
    )
    print(
        "Equity inicial: "
        f"${report.initial_equity:.2f}"
    )
    print(
        "Equity final: "
        f"${report.final_equity:.2f}"
    )
    print(
        "Beneficio neto: "
        f"${report.net_profit:.2f}"
    )
    print(
        "Rendimiento: "
        f"{report.return_percent:.2f}%"
    )
    print(
        "Pico de equity: "
        f"${report.peak_equity:.2f}"
    )
    print(
        "Drawdown máximo: "
        f"${report.max_drawdown:.2f}"
    )
    print(
        "Drawdown máximo %: "
        f"{report.max_drawdown_percent:.2f}%"
    )
    print(
        "Exposición bruta promedio: "
        f"${report.average_gross_exposure:.2f}"
    )
    print(
        "Exposición bruta máxima: "
        f"${report.max_gross_exposure:.2f}"
    )
    print(
        "Exposición neta promedio: "
        f"${report.average_net_exposure:.2f}"
    )

    PortfolioJsonExporter().export_json(
        report=report,
        file_path=json_path,
    )

    PortfolioCsvExporter().export_csv(
        report=report,
        summary_file=summary_path,
        snapshots_file=snapshots_path,
    )

    PortfolioDashboardExporter().export_dashboard(
        report=report,
        file_path=dashboard_path,
    )


if __name__ == "__main__":
    main()
