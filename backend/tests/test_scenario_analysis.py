import pytest

from backend.portfolio.scenario_analysis import (
    ScenarioAnalysis,
)


def build_weights() -> dict[str, float]:
    return {
        "AAPL": 0.4,
        "MSFT": 0.35,
        "NVDA": 0.25,
    }


def test_lists_available_scenarios():
    scenarios = (
        ScenarioAnalysis()
        .available_scenarios()
    )

    assert "financial_crisis_2008" in scenarios
    assert "covid_2020" in scenarios
    assert "technology_shock" in scenarios
    assert "rate_hike" in scenarios


def test_applies_predefined_scenario():
    result = ScenarioAnalysis().calculate(
        weights=build_weights(),
        scenario="technology_shock",
        initial_value=1000.0,
    )

    assert result["scenario"] == (
        "technology_shock"
    )
    assert result["initial_value"] == 1000.0
    assert result["final_value"] < 1000.0
    assert result["percentage_impact"] < 0.0
    assert set(result["asset_impacts"]) == {
        "AAPL",
        "MSFT",
        "NVDA",
    }


def test_returns_scenario_shocks():
    result = ScenarioAnalysis().calculate(
        weights=build_weights(),
        scenario="covid_2020",
    )

    assert set(result["shocks"]) == {
        "AAPL",
        "MSFT",
        "NVDA",
    }


def test_rejects_unknown_scenario():
    with pytest.raises(
        ValueError,
        match="scenario",
    ):
        ScenarioAnalysis().calculate(
            weights=build_weights(),
            scenario="unknown",
        )


def test_rejects_invalid_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        ScenarioAnalysis().calculate(
            weights={
                "AAPL": 0.2,
                "MSFT": 0.2,
            },
            scenario="covid_2020",
        )


def test_rejects_non_positive_initial_value():
    with pytest.raises(
        ValueError,
        match="initial_value",
    ):
        ScenarioAnalysis().calculate(
            weights={
                "AAPL": 1.0,
            },
            scenario="rate_hike",
            initial_value=0.0,
        )
