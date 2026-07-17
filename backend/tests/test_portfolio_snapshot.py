from datetime import datetime, timezone

import pytest

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_snapshot import (
    PortfolioSnapshot,
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
        ]
    )


def test_portfolio_snapshot_calculates_metrics():
    snapshot = PortfolioSnapshot(
        timestamp=datetime(
            2026,
            7,
            16,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        portfolio=build_portfolio(),
        cash=1000.0,
    )

    assert snapshot.cash == 1000.0
    assert snapshot.market_value == 340.0
    assert snapshot.unrealized_pnl == 50.0
    assert snapshot.gross_exposure == 340.0
    assert snapshot.net_exposure == 100.0
    assert snapshot.equity == 1340.0


def test_portfolio_snapshot_preserves_timestamp():
    timestamp = datetime(
        2026,
        7,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    snapshot = PortfolioSnapshot(
        timestamp=timestamp,
        portfolio=build_portfolio(),
        cash=1000.0,
    )

    assert snapshot.timestamp == timestamp


def test_portfolio_snapshot_uses_portfolio_positions():
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        portfolio=build_portfolio(),
        cash=1000.0,
    )

    assert snapshot.total_positions == 2
    assert snapshot.positions == (
        snapshot.portfolio.positions
    )


def test_portfolio_snapshot_handles_empty_portfolio():
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        portfolio=Portfolio(
            positions=[],
        ),
        cash=500.0,
    )

    assert snapshot.total_positions == 0
    assert snapshot.market_value == 0.0
    assert snapshot.unrealized_pnl == 0.0
    assert snapshot.gross_exposure == 0.0
    assert snapshot.net_exposure == 0.0
    assert snapshot.equity == 500.0


def test_portfolio_snapshot_rejects_negative_cash():
    with pytest.raises(
        ValueError,
        match="cash",
    ):
        PortfolioSnapshot(
            timestamp=datetime.now(
                timezone.utc
            ),
            portfolio=build_portfolio(),
            cash=-1.0,
        )


def test_portfolio_snapshot_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioSnapshot(
            timestamp=datetime.now(
                timezone.utc
            ),
            portfolio=object(),
            cash=1000.0,
        )


@pytest.mark.parametrize(
    "timestamp",
    [
        None,
        "2026-07-16",
    ],
)
def test_portfolio_snapshot_rejects_invalid_timestamp(
    timestamp,
):
    with pytest.raises(
        TypeError,
        match="timestamp",
    ):
        PortfolioSnapshot(
            timestamp=timestamp,
            portfolio=build_portfolio(),
            cash=1000.0,
        )


def test_portfolio_snapshot_is_immutable():
    snapshot = PortfolioSnapshot(
        timestamp=datetime.now(timezone.utc),
        portfolio=build_portfolio(),
        cash=1000.0,
    )

    with pytest.raises(
        AttributeError,
    ):
        snapshot.cash = 2000.0
