import pytest

from backend.backtesting.monte_carlo_html_exporter_v2 import (
    MonteCarloHtmlExporterV2,
)
from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)


def build_report() -> MonteCarloReportV2:

    result = MonteCarloSimulationResultV2(
        starting_balance=10000.0,
        final_equities=[
            10150.0,
            10050.0,
        ],
        maximum_drawdowns=[
            70.0,
            120.0,
        ],
        equity_curves=[
            [
                10000.0,
                10100.0,
                10050.0,
                10150.0,
            ],
            [
                10000.0,
                10080.0,
                9950.0,
                10050.0,
            ],
        ],
    )

    return MonteCarloReportV2(
        simulation_result=result,
    )


def test_exports_monte_carlo_report_to_html(
    tmp_path,
):

    output_path = (
        tmp_path
        / "reports"
        / "monte_carlo.html"
    )

    exporter = MonteCarloHtmlExporterV2()

    result = exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.is_file()

    html = output_path.read_text(
        encoding="utf-8",
    )

    assert "<html" in html.lower()
    assert "Monte Carlo Report" in html
    assert "Summary" in html
    assert "Best Final Equity" in html
    assert "Worst Final Equity" in html
    assert "Maximum Drawdowns" in html
    assert "Equity Curves" in html


def test_creates_parent_directories(
    tmp_path,
):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "result.html"
    )

    MonteCarloHtmlExporterV2().export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_rejects_invalid_report(
    tmp_path,
):

    exporter = MonteCarloHtmlExporterV2()

    with pytest.raises(
        TypeError,
        match="MonteCarloReportV2",
    ):
        exporter.export(
            report={},
            output_path=(
                tmp_path
                / "report.html"
            ),
        )


def test_rejects_directory_as_output_path(
    tmp_path,
):

    exporter = MonteCarloHtmlExporterV2()

    with pytest.raises(
        ValueError,
        match="output_path",
    ):
        exporter.export(
            report=build_report(),
            output_path=tmp_path,
        )


def test_export_does_not_modify_report(
    tmp_path,
):

    report = build_report()

    original = report.to_dict()

    MonteCarloHtmlExporterV2().export(
        report=report,
        output_path=(
            tmp_path
            / "report.html"
        ),
    )

    assert report.to_dict() == original
