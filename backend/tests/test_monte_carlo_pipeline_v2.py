from pathlib import Path

import pytest

from backend.backtesting.monte_carlo_pipeline_v2 import (
    MonteCarloPipelineResultV2,
    MonteCarloPipelineV2,
)
from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)


class FakeSimulatorV2:

    def __init__(self) -> None:
        self.calls = []

    def simulate(
        self,
        *,
        trade_pnls,
        starting_balance,
    ) -> MonteCarloSimulationResultV2:

        normalized_trade_pnls = list(
            trade_pnls
        )

        self.calls.append(
            {
                "trade_pnls": normalized_trade_pnls,
                "starting_balance": float(
                    starting_balance
                ),
            }
        )

        return MonteCarloSimulationResultV2(
            starting_balance=starting_balance,
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


class FakeJsonExporterV2:

    def __init__(self) -> None:
        self.calls = []

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        normalized_output_path = Path(
            output_path
        )

        self.calls.append(
            {
                "report": report,
                "output_path": normalized_output_path,
            }
        )

        return normalized_output_path


class FakeHtmlExporterV2:

    def __init__(self) -> None:
        self.calls = []

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        normalized_output_path = Path(
            output_path
        )

        self.calls.append(
            {
                "report": report,
                "output_path": normalized_output_path,
            }
        )

        return normalized_output_path


def build_pipeline():

    simulator = FakeSimulatorV2()
    json_exporter = FakeJsonExporterV2()
    html_exporter = FakeHtmlExporterV2()

    pipeline = MonteCarloPipelineV2(
        simulator=simulator,
        json_exporter=json_exporter,
        html_exporter=html_exporter,
    )

    return (
        pipeline,
        simulator,
        json_exporter,
        html_exporter,
    )


def test_runs_complete_monte_carlo_pipeline(
    tmp_path,
):

    (
        pipeline,
        simulator,
        json_exporter,
        html_exporter,
    ) = build_pipeline()

    result = pipeline.run(
        trade_pnls=[
            100.0,
            -50.0,
            80.0,
        ],
        starting_balance=10000.0,
        output_directory=tmp_path,
    )

    assert isinstance(
        result,
        MonteCarloPipelineResultV2,
    )

    assert isinstance(
        result.report,
        MonteCarloReportV2,
    )

    assert result.json_path == (
        tmp_path
        / "monte_carlo.json"
    )

    assert result.html_path == (
        tmp_path
        / "monte_carlo.html"
    )

    assert result.report.summary() == {
        "total_simulations": 2,
        "starting_balance": 10000.0,
        "average_final_equity": 10100.0,
        "worst_maximum_drawdown": 120.0,
        "average_maximum_drawdown": 95.0,
    }

    assert simulator.calls == [
        {
            "trade_pnls": [
                100.0,
                -50.0,
                80.0,
            ],
            "starting_balance": 10000.0,
        },
    ]

    assert len(
        json_exporter.calls
    ) == 1

    assert len(
        html_exporter.calls
    ) == 1


def test_supports_custom_filenames(
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    result = pipeline.run(
        trade_pnls=[
            100.0,
        ],
        starting_balance=10000.0,
        output_directory=tmp_path,
        json_filename="simulation.json",
        html_filename="simulation.html",
    )

    assert result.json_path == (
        tmp_path
        / "simulation.json"
    )

    assert result.html_path == (
        tmp_path
        / "simulation.html"
    )


def test_rejects_invalid_simulator():

    with pytest.raises(
        TypeError,
        match="simulate",
    ):
        MonteCarloPipelineV2(
            simulator=object(),
            json_exporter=FakeJsonExporterV2(),
            html_exporter=FakeHtmlExporterV2(),
        )


def test_rejects_invalid_json_exporter():

    with pytest.raises(
        TypeError,
        match="export",
    ):
        MonteCarloPipelineV2(
            simulator=FakeSimulatorV2(),
            json_exporter=object(),
            html_exporter=FakeHtmlExporterV2(),
        )


def test_rejects_invalid_html_exporter():

    with pytest.raises(
        TypeError,
        match="export",
    ):
        MonteCarloPipelineV2(
            simulator=FakeSimulatorV2(),
            json_exporter=FakeJsonExporterV2(),
            html_exporter=object(),
        )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_json_filename(
    filename,
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    with pytest.raises(
        ValueError,
        match="json_filename",
    ):
        pipeline.run(
            trade_pnls=[
                100.0,
            ],
            starting_balance=10000.0,
            output_directory=tmp_path,
            json_filename=filename,
        )


@pytest.mark.parametrize(
    "filename",
    [
        "",
        "   ",
    ],
)
def test_rejects_empty_html_filename(
    filename,
    tmp_path,
):

    pipeline, _, _, _ = build_pipeline()

    with pytest.raises(
        ValueError,
        match="html_filename",
    ):
        pipeline.run(
            trade_pnls=[
                100.0,
            ],
            starting_balance=10000.0,
            output_directory=tmp_path,
            html_filename=filename,
        )
