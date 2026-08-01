import json

from backend.backtesting.monte_carlo_html_exporter_v2 import (
    MonteCarloHtmlExporterV2,
)
from backend.backtesting.monte_carlo_json_exporter_v2 import (
    MonteCarloJsonExporterV2,
)
from backend.backtesting.monte_carlo_pipeline_v2 import (
    MonteCarloPipelineResultV2,
    MonteCarloPipelineV2,
)
from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulatorV2,
)


def build_trade_pnls():

    return [
        120.0,
        -60.0,
        90.0,
        -40.0,
        150.0,
        -80.0,
        70.0,
        110.0,
        -50.0,
        130.0,
    ]


def test_real_monte_carlo_pipeline_exports_reports(
    tmp_path,
):

    pipeline = MonteCarloPipelineV2(
        simulator=MonteCarloSimulatorV2(
            simulations=100,
            random_seed=42,
        ),
        json_exporter=(
            MonteCarloJsonExporterV2()
        ),
        html_exporter=(
            MonteCarloHtmlExporterV2()
        ),
    )

    output_directory = (
        tmp_path
        / "monte_carlo"
    )

    result = pipeline.run(
        trade_pnls=build_trade_pnls(),
        starting_balance=17000.0,
        output_directory=output_directory,
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
        output_directory
        / "monte_carlo.json"
    )

    assert result.html_path == (
        output_directory
        / "monte_carlo.html"
    )

    assert result.json_path.exists()
    assert result.html_path.exists()

    summary = result.report.summary()

    assert summary[
        "total_simulations"
    ] == 100

    assert summary[
        "starting_balance"
    ] == 17000.0

    expected_final_equity = (
        17000.0
        + sum(
            build_trade_pnls()
        )
    )

    assert summary[
        "average_final_equity"
    ] == expected_final_equity

    assert summary[
        "worst_maximum_drawdown"
    ] >= 0.0

    assert summary[
        "average_maximum_drawdown"
    ] >= 0.0

    assert (
        result.report.best_final_equity()
        == expected_final_equity
    )

    assert (
        result.report.worst_final_equity()
        == expected_final_equity
    )

    payload = json.loads(
        result.json_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload[
        "summary"
    ] == summary

    assert len(
        payload["final_equities"]
    ) == 100

    assert len(
        payload["maximum_drawdowns"]
    ) == 100

    assert len(
        payload["equity_curves"]
    ) == 100

    assert all(
        len(curve)
        == len(
            build_trade_pnls()
        ) + 1
        for curve in payload[
            "equity_curves"
        ]
    )

    html = result.html_path.read_text(
        encoding="utf-8",
    )

    assert "Monte Carlo Report" in html
    assert "Summary" in html
    assert "Best Final Equity" in html
    assert "Worst Final Equity" in html
    assert "Maximum Drawdowns" in html
    assert "Equity Curves" in html


def test_real_monte_carlo_pipeline_is_reproducible(
    tmp_path,
):

    first_pipeline = MonteCarloPipelineV2(
        simulator=MonteCarloSimulatorV2(
            simulations=50,
            random_seed=123,
        ),
        json_exporter=(
            MonteCarloJsonExporterV2()
        ),
        html_exporter=(
            MonteCarloHtmlExporterV2()
        ),
    )

    second_pipeline = MonteCarloPipelineV2(
        simulator=MonteCarloSimulatorV2(
            simulations=50,
            random_seed=123,
        ),
        json_exporter=(
            MonteCarloJsonExporterV2()
        ),
        html_exporter=(
            MonteCarloHtmlExporterV2()
        ),
    )

    first_result = first_pipeline.run(
        trade_pnls=build_trade_pnls(),
        starting_balance=17000.0,
        output_directory=(
            tmp_path
            / "first"
        ),
    )

    second_result = second_pipeline.run(
        trade_pnls=build_trade_pnls(),
        starting_balance=17000.0,
        output_directory=(
            tmp_path
            / "second"
        ),
    )

    assert (
        first_result.report.to_dict()
        == second_result.report.to_dict()
    )
