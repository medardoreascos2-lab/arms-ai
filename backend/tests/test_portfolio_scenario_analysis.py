import pytest

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_scenario_analysis import (
    PortfolioScenarioAnalysis,
)


def build_portfolio() -> Portfolio:
    return Portfolio(
        positions=[
            PortfolioPosition(
                symbol="NQ",
                quantity=2.0,
                average_price=100.0,
                current_price=110.0,
            ),
            PortfolioPosition(
                symbol="ES",
                quantity=-3.0,
                average_price=50.0,
                current_price=40.0,
            ),
            PortfolioPosition(
                symbol="CL",
                quantity=1.0,
                average_price=70.0,
                current_price=75.0,
            ),
        ]
    )


def build_scenarios():
    return {
        "market_crash": {
            "global_shock": -0.20,
        },
        "bull_market": {
            "global_shock": 0.15,
        },
        "energy_shock": {
            "shocks": {
                "NQ": -0.05,
                "ES": 0.05,
                "CL": 0.40,
            },
        },
    }


def test_scenario_analysis_runs_all_scenarios():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    assert analysis.scenario_count == 3
    assert tuple(analysis.results) == (
        "market_crash",
        "bull_market",
        "energy_shock",
    )


def test_scenario_analysis_detects_best_scenario():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    assert analysis.best_scenario == "bull_market"
    assert analysis.best_change == pytest.approx(
        26.25,
        abs=0.01,
    )


def test_scenario_analysis_detects_worst_scenario():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    assert analysis.worst_scenario == "market_crash"
    assert analysis.worst_change == pytest.approx(
        -35.0,
        abs=0.01,
    )


def test_scenario_analysis_calculates_summary():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    assert analysis.average_change == pytest.approx(
        1.42,
        abs=0.01,
    )
    assert analysis.median_change == pytest.approx(
        13.0,
        abs=0.01,
    )


def test_scenario_analysis_exposes_individual_results():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    crash = analysis.results["market_crash"]

    assert crash.absolute_change == -35.0
    assert crash.worst_affected_asset == "NQ"

    energy = analysis.results["energy_shock"]

    assert energy.impacts["CL"] == 30.0
    assert energy.absolute_change == 13.0


def test_scenario_analysis_rejects_empty_scenarios():
    with pytest.raises(
        ValueError,
        match="scenarios",
    ):
        PortfolioScenarioAnalysis.run(
            portfolio=build_portfolio(),
            scenarios={},
        )


def test_scenario_analysis_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioScenarioAnalysis.run(
            portfolio=object(),
            scenarios=build_scenarios(),
        )


def test_scenario_analysis_rejects_invalid_scenario():
    with pytest.raises(
        ValueError,
        match="scenario",
    ):
        PortfolioScenarioAnalysis.run(
            portfolio=build_portfolio(),
            scenarios={
                "invalid": {},
            },
        )


def test_scenario_analysis_is_immutable():
    analysis = PortfolioScenarioAnalysis.run(
        portfolio=build_portfolio(),
        scenarios=build_scenarios(),
    )

    with pytest.raises(
        AttributeError,
    ):
        analysis.best_scenario = "other"
