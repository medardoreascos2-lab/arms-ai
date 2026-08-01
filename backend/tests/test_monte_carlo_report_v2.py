import pytest

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)


def build_result():

    return MonteCarloSimulationResultV2(
        starting_balance=10000.0,
        equity_curves=[
            [10000.0, 10100.0, 10050.0],
            [10000.0, 10080.0, 10150.0],
        ],
        final_equities=[
            10050.0,
            10150.0,
        ],
        maximum_drawdowns=[
            50.0,
            20.0,
        ],
    )


def test_builds_report():

    report = MonteCarloReportV2(
        simulation_result=build_result(),
    )

    assert report.total_simulations == 2

    assert report.summary()["starting_balance"] == 10000.0

    assert report.summary()["average_final_equity"] == pytest.approx(
        10100.0
    )


def test_exposes_best_and_worst_equity():

    report = MonteCarloReportV2(
        simulation_result=build_result(),
    )

    assert report.best_final_equity() == 10150.0
    assert report.worst_final_equity() == 10050.0


def test_to_dict_returns_complete_report():

    report = MonteCarloReportV2(
        simulation_result=build_result(),
    )

    payload = report.to_dict()

    assert payload["summary"]["total_simulations"] == 2

    assert payload["best_final_equity"] == 10150.0

    assert payload["worst_final_equity"] == 10050.0

    assert len(
        payload["equity_curves"]
    ) == 2


def test_to_dict_returns_safe_copy():

    report = MonteCarloReportV2(
        simulation_result=build_result(),
    )

    payload = report.to_dict()

    payload["equity_curves"][0][0] = 0.0

    assert (
        report.to_dict()["equity_curves"][0][0]
        == 10000.0
    )


def test_rejects_invalid_result():

    with pytest.raises(
        TypeError,
        match="MonteCarloSimulationResultV2",
    ):
        MonteCarloReportV2(
            simulation_result={},
        )
