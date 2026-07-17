import pytest

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_stress_test import (
    PortfolioStressTest,
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


def test_stress_test_applies_asset_specific_shocks():
    report = PortfolioStressTest.run(
        portfolio=build_portfolio(),
        shocks={
            "NQ": -0.10,
            "ES": 0.05,
            "CL": -0.20,
        },
    )

    assert report.initial_market_value == 415.0
    assert report.stressed_market_value == pytest.approx(
        372.0,
        abs=0.01,
    )
    assert report.absolute_change == pytest.approx(
        -43.0,
        abs=0.01,
    )
    assert report.change_percent == pytest.approx(
        -10.36,
        abs=0.01,
    )


def test_stress_test_calculates_position_impacts():
    report = PortfolioStressTest.run(
        portfolio=build_portfolio(),
        shocks={
            "NQ": -0.10,
            "ES": 0.05,
            "CL": -0.20,
        },
    )

    assert report.impacts["NQ"] == pytest.approx(
        -22.0,
        abs=0.01,
    )
    assert report.impacts["ES"] == pytest.approx(
        -6.0,
        abs=0.01,
    )
    assert report.impacts["CL"] == pytest.approx(
        -15.0,
        abs=0.01,
    )

    assert report.worst_affected_asset == "NQ"
    assert report.worst_asset_impact == -22.0


def test_stress_test_supports_global_shock():
    report = PortfolioStressTest.run(
        portfolio=build_portfolio(),
        global_shock=-0.10,
    )

    assert report.stressed_market_value == pytest.approx(
        397.5,
        abs=0.01,
    )
    assert report.absolute_change == pytest.approx(
        -17.5,
        abs=0.01,
    )


def test_stress_test_asset_shock_overrides_global_shock():
    report = PortfolioStressTest.run(
        portfolio=build_portfolio(),
        global_shock=-0.10,
        shocks={
            "NQ": -0.20,
        },
    )

    assert report.impacts["NQ"] == pytest.approx(
        -44.0,
        abs=0.01,
    )
    assert report.impacts["ES"] == pytest.approx(
        12.0,
        abs=0.01,
    )
    assert report.impacts["CL"] == pytest.approx(
        -7.5,
        abs=0.01,
    )


def test_stress_test_handles_empty_portfolio():
    report = PortfolioStressTest.run(
        portfolio=Portfolio(
            positions=[],
        ),
        global_shock=-0.20,
    )

    assert report.initial_market_value == 0.0
    assert report.stressed_market_value == 0.0
    assert report.absolute_change == 0.0
    assert report.change_percent == 0.0
    assert report.impacts == {}
    assert report.worst_affected_asset is None
    assert report.worst_asset_impact == 0.0


def test_stress_test_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioStressTest.run(
            portfolio=object(),
            global_shock=-0.10,
        )


def test_stress_test_rejects_missing_shocks():
    with pytest.raises(
        ValueError,
        match="shock",
    ):
        PortfolioStressTest.run(
            portfolio=build_portfolio(),
        )


@pytest.mark.parametrize(
    "shock",
    [
        -1.01,
        1.01,
    ],
)
def test_stress_test_rejects_invalid_shock(
    shock,
):
    with pytest.raises(
        ValueError,
        match="shock",
    ):
        PortfolioStressTest.run(
            portfolio=build_portfolio(),
            global_shock=shock,
        )


def test_stress_test_is_immutable():
    report = PortfolioStressTest.run(
        portfolio=build_portfolio(),
        global_shock=-0.10,
    )

    with pytest.raises(
        AttributeError,
    ):
        report.absolute_change = 0.0
