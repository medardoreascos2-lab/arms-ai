import pytest

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)


def build_positions():
    return [
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
            symbol="YM",
            quantity=1.0,
            average_price=200.0,
            current_price=220.0,
        ),
    ]


def test_portfolio_calculates_aggregate_metrics():
    portfolio = Portfolio(
        positions=build_positions(),
    )

    assert portfolio.total_positions == 3
    assert portfolio.total_cost_basis == 550.0
    assert portfolio.total_market_value == 560.0
    assert portfolio.total_unrealized_pnl == 70.0


def test_portfolio_calculates_exposures():
    portfolio = Portfolio(
        positions=build_positions(),
    )

    assert portfolio.long_exposure == 440.0
    assert portfolio.short_exposure == 120.0
    assert portfolio.gross_exposure == 560.0
    assert portfolio.net_exposure == 320.0


def test_portfolio_calculates_position_weights():
    portfolio = Portfolio(
        positions=build_positions(),
    )

    assert portfolio.weights["NQ"] == pytest.approx(
        39.29,
        abs=0.01,
    )
    assert portfolio.weights["ES"] == pytest.approx(
        21.43,
        abs=0.01,
    )
    assert portfolio.weights["YM"] == pytest.approx(
        39.29,
        abs=0.01,
    )


def test_portfolio_ignores_flat_positions_in_exposure():
    portfolio = Portfolio(
        positions=[
            PortfolioPosition(
                symbol="NQ",
                quantity=0.0,
                average_price=100.0,
                current_price=100.0,
            )
        ],
    )

    assert portfolio.long_exposure == 0.0
    assert portfolio.short_exposure == 0.0
    assert portfolio.gross_exposure == 0.0
    assert portfolio.net_exposure == 0.0
    assert portfolio.weights == {}


def test_portfolio_handles_empty_positions():
    portfolio = Portfolio(
        positions=[],
    )

    assert portfolio.total_positions == 0
    assert portfolio.total_cost_basis == 0.0
    assert portfolio.total_market_value == 0.0
    assert portfolio.total_unrealized_pnl == 0.0
    assert portfolio.long_exposure == 0.0
    assert portfolio.short_exposure == 0.0
    assert portfolio.gross_exposure == 0.0
    assert portfolio.net_exposure == 0.0
    assert portfolio.weights == {}


def test_portfolio_rejects_duplicate_symbols():
    positions = [
        PortfolioPosition(
            symbol="NQ",
            quantity=1.0,
            average_price=100.0,
            current_price=110.0,
        ),
        PortfolioPosition(
            symbol="NQ",
            quantity=2.0,
            average_price=105.0,
            current_price=115.0,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        Portfolio(
            positions=positions,
        )


def test_portfolio_rejects_invalid_position_type():
    with pytest.raises(
        TypeError,
        match="PortfolioPosition",
    ):
        Portfolio(
            positions=[
                object(),
            ],
        )


def test_portfolio_preserves_position_copy():
    positions = build_positions()

    portfolio = Portfolio(
        positions=positions,
    )

    positions.clear()

    assert portfolio.total_positions == 3


def test_portfolio_positions_are_immutable():
    portfolio = Portfolio(
        positions=build_positions(),
    )

    with pytest.raises(
        AttributeError,
    ):
        portfolio.positions = ()
