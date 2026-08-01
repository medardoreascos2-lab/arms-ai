from pathlib import Path

import pytest

from backend.backtesting.backtest_html_exporter_v2 import (
    BacktestHtmlExporterV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


def build_report():

    return BacktestReportV2(
        candles_processed=50,
        decisions=[{"action": "BUY"}],
        trade_plans=[{"entry_price": 20000.0}],
        signals=[{"symbol": "NQ"}],
        submission_results=[{"accepted": True}],
        position_updates=[{"updated": True}],
        trade_history=[
            {
                "trade_id": "T-1",
                "symbol": "NQ",
                "result": "WIN",
                "realized_pnl": 100.0,
            },
        ],
        performance_metrics={
            "total_trades": 1,
            "wins": 1,
            "losses": 0,
            "net_pnl": 100.0,
            "win_rate": 1.0,
        },
        active_positions=[],
    )


def test_exports_html_report(tmp_path):

    exporter = BacktestHtmlExporterV2()

    output = (
        tmp_path
        / "reports"
        / "backtest.html"
    )

    result = exporter.export(
        report=build_report(),
        output_path=output,
    )

    assert result == output
    assert output.exists()

    html = output.read_text(
        encoding="utf-8",
    )

    assert "<html" in html.lower()
    assert "Backtest Report" in html
    assert "candles_processed" in html
    assert "trade_history" in html


def test_creates_parent_directory(tmp_path):

    exporter = BacktestHtmlExporterV2()

    output = (
        tmp_path
        / "nested"
        / "reports"
        / "report.html"
    )

    exporter.export(
        report=build_report(),
        output_path=output,
    )

    assert output.exists()


def test_rejects_invalid_report(tmp_path):

    exporter = BacktestHtmlExporterV2()

    with pytest.raises(
        TypeError,
    ):
        exporter.export(
            report={},
            output_path=tmp_path / "a.html",
        )


def test_rejects_directory(tmp_path):

    exporter = BacktestHtmlExporterV2()

    with pytest.raises(
        ValueError,
    ):
        exporter.export(
            report=build_report(),
            output_path=tmp_path,
        )
