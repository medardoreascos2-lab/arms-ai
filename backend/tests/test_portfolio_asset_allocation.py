import pytest

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_asset_allocation import (
    PortfolioAssetAllocation,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
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


def test_asset_allocation_calculates_weights():
    allocation = PortfolioAssetAllocation.from_portfolio(
        build_portfolio()
    )

    assert allocation.total_market_value == 415.0

    assert allocation.weights["NQ"] == pytest.approx(
        53.01,
        abs=0.01,
    )
    assert allocation.weights["ES"] == pytest.approx(
        28.92,
        abs=0.01,
    )
    assert allocation.weights["CL"] == pytest.approx(
        18.07,
        abs=0.01,
    )


def test_asset_allocation_orders_assets_by_weight():
    allocation = PortfolioAssetAllocation.from_portfolio(
        build_portfolio()
    )

    assert allocation.ordered_symbols == (
        "NQ",
        "ES",
        "CL",
    )


def test_asset_allocation_detects_largest_and_smallest():
    allocation = PortfolioAssetAllocation.from_portfolio(
        build_portfolio()
    )

    assert allocation.largest_symbol == "NQ"
    assert allocation.largest_weight == pytest.approx(
        53.01,
        abs=0.01,
    )

    assert allocation.smallest_symbol == "CL"
    assert allocation.smallest_weight == pytest.approx(
        18.07,
        abs=0.01,
    )


def test_asset_allocation_calculates_concentration():
    allocation = PortfolioAssetAllocation.from_portfolio(
        build_portfolio()
    )

    assert allocation.top_1_concentration == pytest.approx(
        53.01,
        abs=0.01,
    )

    assert allocation.top_2_concentration == pytest.approx(
        81.93,
        abs=0.01,
    )


def test_asset_allocation_handles_empty_portfolio():
    allocation = PortfolioAssetAllocation.from_portfolio(
        Portfolio(
            positions=[],
        )
    )

    assert allocation.total_market_value == 0.0
    assert allocation.weights == {}
    assert allocation.ordered_symbols == ()
    assert allocation.largest_symbol is None
    assert allocation.smallest_symbol is None
    assert allocation.largest_weight == 0.0
    assert allocation.smallest_weight == 0.0
    assert allocation.top_1_concentration == 0.0
    assert allocation.top_2_concentration == 0.0


def test_asset_allocation_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioAssetAllocation.from_portfolio(
            object(),
        )


def test_asset_allocation_is_immutable():
    allocation = PortfolioAssetAllocation.from_portfolio(
        build_portfolio()
    )

    with pytest.raises(
        AttributeError,
    ):
        allocation.total_market_value = 0.0
