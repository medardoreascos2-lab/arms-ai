from pathlib import Path

from backend.backtesting.backtest_dashboard_exporter import (
    BacktestDashboardExporter,
)
from backend.backtesting.equity_curve import EquityCurve
from backend.models.backtest_result import BacktestResult
from backend.models.backtest_statistics import BacktestStatistics


class SimulatedTradeStub:
    def __init__(
        self,
        *,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        direction="BUY",
        entry_price=21600.0,
        stop_loss=21595.0,
        take_profit=21610.0,
        exit_price=21610.0,
        result="TAKE PROFIT",
        contracts=2,
        pnl=40.0,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.exit_price = exit_price
        self.result = result
        self.contracts = contracts
        self.pnl = pnl


def build_result() -> BacktestResult:
    result = BacktestResult(
        total_candles=300,
        total_signals=250,
        authorized_trades=2,
        blocked_signals=248,
        initial_balance=17000.0,
    )

    result.trades = [
        SimulatedTradeStub(
            pnl=40.0,
        ),
        SimulatedTradeStub(
            direction="SELL",
            entry_price=21620.0,
            stop_loss=21625.0,
            take_profit=21610.0,
            exit_price=21625.0,
            result="STOP LOSS",
            pnl=-20.0,
        ),
    ]

    result.statistics = BacktestStatistics(
        total_trades=2,
        winning_trades=1,
        losing_trades=1,
        breakeven_trades=0,
        gross_profit=40.0,
        gross_loss=20.0,
        net_profit=20.0,
        win_rate=50.0,
        profit_factor=2.0,
        expectancy=10.0,
        max_drawdown=20.0,
    )

    result.equity_curve = EquityCurve(
        initial_balance=17000.0,
    )
    result.equity_curve.add_trade(40.0)
    result.equity_curve.add_trade(-20.0)

    return result


def test_dashboard_exporter_writes_html(tmp_path):
    file_path = tmp_path / "backtest_dashboard.html"

    returned_path = BacktestDashboardExporter().export_html(
        result=build_result(),
        file_path=file_path,
        source_file="data/nq_1m_mixed_300.csv",
        journal_path="data/reports/trade_journal.csv",
        equity_path="data/reports/equity_curve.csv",
        summary_path="data/reports/backtest_summary.json",
    )

    assert returned_path == file_path
    assert file_path.exists()

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "<!DOCTYPE html>" in html
    assert "ARMS AI Backtest Dashboard" in html
    assert "NASDAQ / NQ" in html
    assert "Balance final" in html
    assert "$17020.00" in html
    assert "Win rate" in html
    assert "50.00%" in html
    assert "Profit factor" in html
    assert "2.00" in html


def test_dashboard_exporter_contains_trade_table(tmp_path):
    file_path = tmp_path / "dashboard.html"

    BacktestDashboardExporter().export_html(
        result=build_result(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "<table" in html
    assert "BUY" in html
    assert "SELL" in html
    assert "TAKE PROFIT" in html
    assert "STOP LOSS" in html
    assert "$40.00" in html
    assert "$-20.00" in html


def test_dashboard_exporter_contains_equity_chart_data(
    tmp_path,
):
    file_path = tmp_path / "dashboard.html"

    BacktestDashboardExporter().export_html(
        result=build_result(),
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "17000.0" in html
    assert "17040.0" in html
    assert "17020.0" in html
    assert "equity-chart" in html


def test_dashboard_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "backtest_dashboard.html"
    )

    BacktestDashboardExporter().export_html(
        result=build_result(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_dashboard_exporter_contains_report_links(
    tmp_path,
):
    file_path = tmp_path / "dashboard.html"

    BacktestDashboardExporter().export_html(
        result=build_result(),
        file_path=file_path,
        journal_path="trade_journal.csv",
        equity_path="equity_curve.csv",
        summary_path="backtest_summary.json",
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert 'href="trade_journal.csv"' in html
    assert 'href="equity_curve.csv"' in html
    assert 'href="backtest_summary.json"' in html


def test_dashboard_exporter_handles_no_trades(
    tmp_path,
):
    result = BacktestResult(
        initial_balance=17000.0,
    )

    file_path = tmp_path / "dashboard.html"

    BacktestDashboardExporter().export_html(
        result=result,
        file_path=file_path,
    )

    html = file_path.read_text(
        encoding="utf-8",
    )

    assert "No hay operaciones registradas." in html
