import json

import pytest

from backend.backtesting.monte_carlo_json_exporter_v2 import (
    MonteCarloJsonExporterV2,
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


def test_exports_monte_carlo_report_to_json(
    tmp_path,
):

    output_path = (
        tmp_path
        / "reports"
        / "monte_carlo.json"
    )

    exporter = MonteCarloJsonExporterV2()

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
        "total_simulations": 2,
        "starting_balance": 10000.0,
        "average_final_equity": 10100.0,
        "worst_maximum_drawdown": 120.0,
        "average_maximum_drawdown": 95.0,
    }

    assert (
        payload["best_final_equity"]
        == 10150.0
    )

    assert (
        payload["worst_final_equity"]
        == 10050.0
    )

    assert len(
        payload["equity_curves"]
    ) == 2


def test_creates_parent_directories(
    tmp_path,
):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "result.json"
    )

    MonteCarloJsonExporterV2().export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_uses_readable_indented_json(
    tmp_path,
):

    output_path = (
        tmp_path
        / "monte_carlo.json"
    )

    exporter = MonteCarloJsonExporterV2(
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


def test_rejects_invalid_report(
    tmp_path,
):

    exporter = MonteCarloJsonExporterV2()

    with pytest.raises(
        TypeError,
        match="MonteCarloReportV2",
    ):
        exporter.export(
            report={},
            output_path=(
                tmp_path
                / "report.json"
            ),
        )


def test_rejects_directory_as_output_path(
    tmp_path,
):

    exporter = MonteCarloJsonExporterV2()

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

    MonteCarloJsonExporterV2().export(
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
def test_rejects_invalid_indent(
    indent,
):

    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        MonteCarloJsonExporterV2(
            indent=indent,
        )
