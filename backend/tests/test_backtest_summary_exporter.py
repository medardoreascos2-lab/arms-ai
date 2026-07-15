import json
from pathlib import Path

from backend.backtesting.equity_curve import EquityCurve
from backend.backtesting.backtest_summary_exporter import (
    BacktestSummaryExporter,
)
from backend.models.backtest_result import BacktestResult
from backend.models.backtest_statistics import BacktestStatistics


def build_result() -> BacktestResult:
    result = BacktestResult(
        total_candles=300,
        total_signals=250,
        authorized_trades=8,
        blocked_signals=242,
        initial_balance=17000.0,
    )

    result.trades = [
        object(),
        object(),
    ]

    result.statistics = BacktestStatistics(
        total_trades=8,
        winning_trades=5,
        losing_trades=3,
        breakeven_trades=0,
        gross_profit=66.44,
        gross_loss=10.72,
        net_profit=55.72,
        win_rate=62.5,
        profit_factor=6.2,
        expectancy=6.97,
        max_drawdown=4.56,
    )

    result.equity_curve = EquityCurve(
        initial_balance=17000.0,
    )
    result.equity_curve.add_trade(60.28)
    result.equity_curve.add_trade(-4.56)

    return result


def test_backtest_summary_exporter_writes_json(
    tmp_path,
):
    file_path = tmp_path / "backtest_summary.json"

    exporter = BacktestSummaryExporter()

    returned_path = exporter.export_json(
        result=build_result(),
        file_path=file_path,
        source_file="data/nq_1m_mixed_300.csv",
        journal_path="data/reports/trade_journal.csv",
        equity_path="data/reports/equity_curve.csv",
    )

    assert returned_path == file_path
    assert file_path.exists()

    data = json.loads(
        file_path.read_text(encoding="utf-8")
    )

    assert data["source_file"] == (
        "data/nq_1m_mixed_300.csv"
    )

    assert data["backtest"]["total_candles"] == 300
    assert data["backtest"]["total_signals"] == 250
    assert data["backtest"]["authorized_trades"] == 8
    assert data["backtest"]["blocked_signals"] == 242
    assert data["backtest"]["registered_trades"] == 2

    assert data["equity"]["initial_balance"] == 17000.0
    assert data["equity"]["final_balance"] == 17055.72
    assert data["equity"]["peak_balance"] == 17060.28
    assert data["equity"]["max_drawdown"] == 4.56

    assert data["statistics"]["winning_trades"] == 5
    assert data["statistics"]["losing_trades"] == 3
    assert data["statistics"]["net_profit"] == 55.72
    assert data["statistics"]["win_rate"] == 62.5
    assert data["statistics"]["profit_factor"] == 6.2

    assert data["reports"]["trade_journal"] == (
        "data/reports/trade_journal.csv"
    )
    assert data["reports"]["equity_curve"] == (
        "data/reports/equity_curve.csv"
    )


def test_backtest_summary_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "backtest_summary.json"
    )

    BacktestSummaryExporter().export_json(
        result=build_result(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_backtest_summary_exporter_handles_missing_paths(
    tmp_path,
):
    file_path = tmp_path / "summary.json"

    BacktestSummaryExporter().export_json(
        result=build_result(),
        file_path=file_path,
    )

    data = json.loads(
        file_path.read_text(encoding="utf-8")
    )

    assert data["source_file"] is None
    assert data["reports"]["trade_journal"] is None
    assert data["reports"]["equity_curve"] is None


def test_backtest_summary_exporter_uses_valid_json(
    tmp_path,
):
    file_path = tmp_path / "summary.json"

    BacktestSummaryExporter().export_json(
        result=build_result(),
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert isinstance(data, dict)
    assert set(data) == {
        "source_file",
        "backtest",
        "equity",
        "statistics",
        "reports",
    }
