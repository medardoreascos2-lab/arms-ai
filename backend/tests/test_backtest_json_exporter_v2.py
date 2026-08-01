import json

import pytest

from backend.backtesting.backtest_json_exporter_v2 import (
    BacktestJsonExporterV2,
)
from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


def build_report() -> BacktestReportV2:

    return BacktestReportV2(
        candles_processed=50,
        decisions=[
            {
                "action": "BUY",
            },
        ],
        trade_plans=[
            {
                "entry_price": 20000.0,
            },
        ],
        signals=[
            {
                "symbol": "NQ",
            },
        ],
        submission_results=[
            {
                "accepted": True,
            },
        ],
        position_updates=[
            {
                "updated": True,
            },
        ],
        trade_history=[
            {
                "trade_id": "T-1",
                "realized_pnl": 100.0,
            },
        ],
        performance_metrics={
            "total_trades": 1,
            "wins": 1,
            "net_pnl": 100.0,
            "equity_curve": [
                17000.0,
                17100.0,
            ],
        },
        active_positions=[],
    )


def test_exports_report_to_json(tmp_path):

    output_path = (
        tmp_path
        / "reports"
        / "backtest.json"
    )

    exporter = BacktestJsonExporterV2()

    result = exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.is_file()

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["summary"] == {
        "candles_processed": 50,
        "decisions": 1,
        "trade_plans": 1,
        "signals": 1,
        "submissions": 1,
        "position_updates": 1,
        "closed_trades": 1,
        "active_positions": 0,
    }

    assert payload["candles_processed"] == 50
    assert payload["decisions"][0]["action"] == "BUY"
    assert payload["trade_history"][0]["trade_id"] == "T-1"
    assert payload["performance_metrics"]["net_pnl"] == 100.0


def test_creates_parent_directories(tmp_path):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "result.json"
    )

    exporter = BacktestJsonExporterV2()

    exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_uses_readable_indented_json(tmp_path):

    output_path = tmp_path / "report.json"

    exporter = BacktestJsonExporterV2(
        indent=2,
    )

    exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    content = output_path.read_text(
        encoding="utf-8",
    )

    assert "\n" in content
    assert '  "summary"' in content


def test_rejects_invalid_report(tmp_path):

    exporter = BacktestJsonExporterV2()

    with pytest.raises(
        TypeError,
        match="BacktestReportV2",
    ):
        exporter.export(
            report={},
            output_path=(
                tmp_path
                / "report.json"
            ),
        )


def test_rejects_directory_as_output_path(tmp_path):

    exporter = BacktestJsonExporterV2()

    with pytest.raises(
        ValueError,
        match="output_path",
    ):
        exporter.export(
            report=build_report(),
            output_path=tmp_path,
        )


def test_export_does_not_modify_report(tmp_path):

    report = build_report()

    original = report.to_dict()

    exporter = BacktestJsonExporterV2()

    exporter.export(
        report=report,
        output_path=(
            tmp_path
            / "report.json"
        ),
    )

    assert report.to_dict() == original


@pytest.mark.parametrize(
    "indent",
    [
        -1,
        "2",
    ],
)
def test_rejects_invalid_indent(indent):

    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        BacktestJsonExporterV2(
            indent=indent,
        )
