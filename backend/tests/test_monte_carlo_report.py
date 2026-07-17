import pytest

from backend.backtesting.monte_carlo_engine import (
    MonteCarloResult,
    MonteCarloSimulation,
)
from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


def build_simulation(
    number,
    final_balance,
    max_drawdown,
    initial_balance=1000.0,
):
    return MonteCarloSimulation(
        simulation_number=number,
        trade_sequence=(),
        initial_balance=initial_balance,
        final_balance=final_balance,
        net_profit=final_balance - initial_balance,
        peak_balance=max(
            initial_balance,
            final_balance,
        ),
        max_drawdown=max_drawdown,
    )


def test_monte_carlo_report_calculates_summary():
    result = MonteCarloResult(
        simulations=[
            build_simulation(1, 900.0, 150.0),
            build_simulation(2, 1000.0, 100.0),
            build_simulation(3, 1100.0, 75.0),
            build_simulation(4, 1200.0, 50.0),
        ]
    )

    report = MonteCarloReport.from_result(
        result=result,
        ruin_balance=800.0,
    )

    assert report.total_simulations == 4
    assert report.average_final_balance == 1050.0
    assert report.median_final_balance == 1050.0
    assert report.best_final_balance == 1200.0
    assert report.worst_final_balance == 900.0

    assert report.average_max_drawdown == pytest.approx(
        93.75
    )
    assert report.worst_max_drawdown == 150.0

    assert report.loss_probability == 25.0
    assert report.ruin_probability == 0.0


def test_monte_carlo_report_detects_ruin_probability():
    result = MonteCarloResult(
        simulations=[
            build_simulation(1, 700.0, 350.0),
            build_simulation(2, 750.0, 300.0),
            build_simulation(3, 900.0, 200.0),
            build_simulation(4, 1100.0, 100.0),
        ]
    )

    report = MonteCarloReport.from_result(
        result=result,
        ruin_balance=800.0,
    )

    assert report.ruin_probability == 50.0
    assert report.loss_probability == 75.0


def test_monte_carlo_report_calculates_percentiles():
    simulations = [
        build_simulation(
            number=index,
            final_balance=1000.0 + index,
            max_drawdown=float(index),
        )
        for index in range(1, 101)
    ]

    report = MonteCarloReport.from_result(
        result=MonteCarloResult(
            simulations=simulations,
        ),
        ruin_balance=500.0,
    )

    assert report.final_balance_percentile_5 == pytest.approx(
        1005.95
    )
    assert report.final_balance_percentile_50 == pytest.approx(
        1050.5
    )
    assert report.final_balance_percentile_95 == pytest.approx(
        1095.05
    )

    assert report.drawdown_percentile_50 == pytest.approx(
        50.5
    )
    assert report.drawdown_percentile_95 == pytest.approx(
        95.05
    )
    assert report.drawdown_percentile_99 == pytest.approx(
        99.01
    )


def test_monte_carlo_report_handles_single_simulation():
    report = MonteCarloReport.from_result(
        result=MonteCarloResult(
            simulations=[
                build_simulation(
                    1,
                    1100.0,
                    50.0,
                )
            ],
        ),
        ruin_balance=800.0,
    )

    assert report.total_simulations == 1
    assert report.average_final_balance == 1100.0
    assert report.median_final_balance == 1100.0
    assert report.final_balance_percentile_5 == 1100.0
    assert report.drawdown_percentile_99 == 50.0


def test_monte_carlo_report_rejects_empty_result():
    with pytest.raises(
        ValueError,
        match="simulations",
    ):
        MonteCarloReport.from_result(
            result=MonteCarloResult(
                simulations=[],
            ),
            ruin_balance=800.0,
        )


@pytest.mark.parametrize(
    "ruin_balance",
    [
        0,
        -100.0,
    ],
)
def test_monte_carlo_report_rejects_invalid_ruin_balance(
    ruin_balance,
):
    result = MonteCarloResult(
        simulations=[
            build_simulation(
                1,
                1100.0,
                50.0,
            )
        ]
    )

    with pytest.raises(
        ValueError,
        match="ruin_balance",
    ):
        MonteCarloReport.from_result(
            result=result,
            ruin_balance=ruin_balance,
        )


def test_monte_carlo_report_preserves_simulation_method():
    result = MonteCarloResult(
        simulations=[
            build_simulation(
                1,
                1100.0,
                50.0,
            )
        ],
        method="bootstrap",
    )

    report = MonteCarloReport.from_result(
        result=result,
        ruin_balance=800.0,
    )

    assert report.method == "bootstrap"


def test_monte_carlo_report_uses_shuffle_as_default_method():
    result = MonteCarloResult(
        simulations=[
            build_simulation(
                1,
                1100.0,
                50.0,
            )
        ],
    )

    report = MonteCarloReport.from_result(
        result=result,
        ruin_balance=800.0,
    )

    assert report.method == "shuffle"
