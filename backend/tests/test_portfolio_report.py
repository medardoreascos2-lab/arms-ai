from datetime import datetime, timedelta, timezone

import pytest

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_report import (
    PortfolioReport,
)
from backend.portfolio.portfolio_snapshot import (
    PortfolioSnapshot,
)


def build_snapshot(
    *,
    timestamp,
    cash,
    positions,
):
    return PortfolioSnapshot(
        timestamp=timestamp,
        portfolio=Portfolio(
            positions=positions,
        ),
        cash=cash,
    )


def test_portfolio_report_calculates_summary():
    start = datetime(
        2026,
        7,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    snapshots = [
        build_snapshot(
            timestamp=start,
            cash=1000.0,
            positions=[],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=1),
            cash=900.0,
            positions=[
                PortfolioPosition(
                    symbol="NQ",
                    quantity=1.0,
                    average_price=100.0,
                    current_price=120.0,
                )
            ],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=2),
            cash=850.0,
            positions=[
                PortfolioPosition(
                    symbol="NQ",
                    quantity=1.0,
                    average_price=100.0,
                    current_price=130.0,
                ),
                PortfolioPosition(
                    symbol="ES",
                    quantity=1.0,
                    average_price=50.0,
                    current_price=70.0,
                ),
            ],
        ),
    ]

    report = PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )

    assert report.total_snapshots == 3
    assert report.initial_equity == 1000.0
    assert report.final_equity == 1050.0
    assert report.net_profit == 50.0
    assert report.return_percent == 5.0
    assert report.peak_equity == 1050.0


def test_portfolio_report_calculates_drawdown():
    start = datetime.now(timezone.utc)

    snapshots = [
        build_snapshot(
            timestamp=start,
            cash=1000.0,
            positions=[],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=1),
            cash=1200.0,
            positions=[],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=2),
            cash=900.0,
            positions=[],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=3),
            cash=1100.0,
            positions=[],
        ),
    ]

    report = PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )

    assert report.peak_equity == 1200.0
    assert report.max_drawdown == 300.0
    assert report.max_drawdown_percent == 25.0


def test_portfolio_report_calculates_exposure_metrics():
    start = datetime.now(timezone.utc)

    snapshots = [
        build_snapshot(
            timestamp=start,
            cash=1000.0,
            positions=[],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=1),
            cash=900.0,
            positions=[
                PortfolioPosition(
                    symbol="NQ",
                    quantity=1.0,
                    average_price=100.0,
                    current_price=100.0,
                )
            ],
        ),
        build_snapshot(
            timestamp=start + timedelta(minutes=2),
            cash=800.0,
            positions=[
                PortfolioPosition(
                    symbol="NQ",
                    quantity=1.0,
                    average_price=100.0,
                    current_price=100.0,
                ),
                PortfolioPosition(
                    symbol="ES",
                    quantity=-2.0,
                    average_price=50.0,
                    current_price=50.0,
                ),
            ],
        ),
    ]

    report = PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )

    assert report.average_gross_exposure == pytest.approx(
        100.0,
        abs=0.01,
    )
    assert report.max_gross_exposure == 200.0

    assert report.average_net_exposure == pytest.approx(
        33.33,
        abs=0.01,
    )
    assert report.max_net_exposure == 100.0
    assert report.min_net_exposure == 0.0


def test_portfolio_report_preserves_snapshot_order():
    start = datetime.now(timezone.utc)

    first = build_snapshot(
        timestamp=start,
        cash=1000.0,
        positions=[],
    )

    second = build_snapshot(
        timestamp=start + timedelta(minutes=1),
        cash=1100.0,
        positions=[],
    )

    report = PortfolioReport.from_snapshots(
        snapshots=[
            first,
            second,
        ],
    )

    assert report.snapshots == (
        first,
        second,
    )


def test_portfolio_report_rejects_empty_snapshots():
    with pytest.raises(
        ValueError,
        match="snapshots",
    ):
        PortfolioReport.from_snapshots(
            snapshots=[],
        )


def test_portfolio_report_rejects_invalid_snapshot_type():
    with pytest.raises(
        TypeError,
        match="PortfolioSnapshot",
    ):
        PortfolioReport.from_snapshots(
            snapshots=[
                object(),
            ],
        )


def test_portfolio_report_rejects_unsorted_snapshots():
    now = datetime.now(timezone.utc)

    first = build_snapshot(
        timestamp=now,
        cash=1000.0,
        positions=[],
    )

    earlier = build_snapshot(
        timestamp=now - timedelta(minutes=1),
        cash=900.0,
        positions=[],
    )

    with pytest.raises(
        ValueError,
        match="timestamp",
    ):
        PortfolioReport.from_snapshots(
            snapshots=[
                first,
                earlier,
            ],
        )


def test_portfolio_report_is_immutable():
    snapshot = build_snapshot(
        timestamp=datetime.now(timezone.utc),
        cash=1000.0,
        positions=[],
    )

    report = PortfolioReport.from_snapshots(
        snapshots=[
            snapshot,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.final_equity = 2000.0
