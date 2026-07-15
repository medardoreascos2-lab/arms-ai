import csv

from backend.backtesting.equity_curve import EquityCurve
from backend.backtesting.equity_curve_exporter import (
    EquityCurveExporter,
)


def test_equity_curve_exporter_writes_csv(tmp_path):
    curve = EquityCurve(initial_balance=17000.0)
    curve.add_trade(100.0)
    curve.add_trade(-50.0)

    file_path = tmp_path / "equity_curve.csv"

    EquityCurveExporter().export_csv(
        equity_curve=curve,
        file_path=file_path,
    )

    assert file_path.exists()

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 3

    assert rows[0]["trade_number"] == "0"
    assert float(rows[0]["balance"]) == 17000.0

    assert rows[1]["trade_number"] == "1"
    assert float(rows[1]["pnl"]) == 100.0
    assert float(rows[1]["balance"]) == 17100.0

    assert rows[2]["trade_number"] == "2"
    assert float(rows[2]["pnl"]) == -50.0
    assert float(rows[2]["balance"]) == 17050.0


def test_equity_curve_exporter_writes_expected_columns(
    tmp_path,
):
    curve = EquityCurve(initial_balance=1000.0)

    file_path = tmp_path / "equity_curve.csv"

    EquityCurveExporter().export_csv(
        equity_curve=curve,
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames == [
            "trade_number",
            "pnl",
            "balance",
            "peak_balance",
            "drawdown",
        ]


def test_equity_curve_exporter_creates_parent_directory(
    tmp_path,
):
    curve = EquityCurve(initial_balance=1000.0)

    file_path = (
        tmp_path
        / "reports"
        / "equity_curve.csv"
    )

    EquityCurveExporter().export_csv(
        equity_curve=curve,
        file_path=file_path,
    )

    assert file_path.exists()
