import pytest

from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)


def test_portfolio_position_calculates_long_metrics():
    position = PortfolioPosition(
        symbol="NQ",
        quantity=2.0,
        average_price=100.0,
        current_price=112.0,
    )

    assert position.symbol == "NQ"
    assert position.side == "long"
    assert position.cost_basis == 200.0
    assert position.market_value == 224.0
    assert position.unrealized_pnl == 24.0
    assert position.return_percent == 12.0


def test_portfolio_position_calculates_short_metrics():
    position = PortfolioPosition(
        symbol="ES",
        quantity=-3.0,
        average_price=50.0,
        current_price=40.0,
    )

    assert position.side == "short"
    assert position.cost_basis == 150.0
    assert position.market_value == 120.0
    assert position.unrealized_pnl == 30.0
    assert position.return_percent == 20.0


def test_portfolio_position_detects_flat_position():
    position = PortfolioPosition(
        symbol="YM",
        quantity=0.0,
        average_price=100.0,
        current_price=100.0,
    )

    assert position.side == "flat"
    assert position.cost_basis == 0.0
    assert position.market_value == 0.0
    assert position.unrealized_pnl == 0.0
    assert position.return_percent == 0.0


def test_portfolio_position_normalizes_symbol():
    position = PortfolioPosition(
        symbol="  nq  ",
        quantity=1.0,
        average_price=100.0,
        current_price=100.0,
    )

    assert position.symbol == "NQ"


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
    ],
)
def test_portfolio_position_rejects_empty_symbol(
    symbol,
):
    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        PortfolioPosition(
            symbol=symbol,
            quantity=1.0,
            average_price=100.0,
            current_price=100.0,
        )


@pytest.mark.parametrize(
    ("average_price", "current_price"),
    [
        (0.0, 100.0),
        (-1.0, 100.0),
        (100.0, 0.0),
        (100.0, -1.0),
    ],
)
def test_portfolio_position_rejects_invalid_prices(
    average_price,
    current_price,
):
    with pytest.raises(
        ValueError,
        match="price",
    ):
        PortfolioPosition(
            symbol="NQ",
            quantity=1.0,
            average_price=average_price,
            current_price=current_price,
        )


def test_portfolio_position_is_immutable():
    position = PortfolioPosition(
        symbol="NQ",
        quantity=1.0,
        average_price=100.0,
        current_price=110.0,
    )

    with pytest.raises(
        AttributeError,
    ):
        position.current_price = 120.0
