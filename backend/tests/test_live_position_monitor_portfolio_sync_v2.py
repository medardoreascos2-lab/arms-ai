import pytest

from backend.portfolio.portfolio_manager_v2 import (
    PortfolioManagerV2,
)
from backend.services.live_position_monitor_v2 import (
    LivePositionMonitorV2,
)


class FakeTradeLifecycleService:

    def __init__(self):
        self.position = {
            "position_id": "pos-1",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "entry_price": 100.0,
            "current_price": 100.0,
            "quantity": 2.0,
            "original_quantity": 2.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "point_value": 2.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "partial_taken": False,
        }

    def get_active_positions(self):
        if self.position["status"] == "OPEN":
            return [
                dict(
                    self.position
                )
            ]

        return []

    def replace_active_position(
        self,
        *,
        position_id,
        position,
    ):
        self.position = dict(
            position
        )

    def update_position(
        self,
        *,
        position_id,
        current_price,
    ):
        self.position[
            "current_price"
        ] = current_price

        if (
            current_price
            >= self.position[
                "take_profit"
            ]
        ):
            self.position[
                "status"
            ] = "CLOSED"

            self.position[
                "exit_price"
            ] = current_price

            self.position[
                "realized_pnl"
            ] = (
                (
                    current_price
                    - self.position[
                        "entry_price"
                    ]
                )
                * self.position[
                    "quantity"
                ]
                * self.position[
                    "point_value"
                ]
            )

        return {
            "updated": True,
            "position": dict(
                self.position
            ),
            "trade_record": None,
            "performance_metrics": None,
            "active_position_removed": (
                self.position[
                    "status"
                ]
                == "CLOSED"
            ),
        }


def build_portfolio_manager(
) -> PortfolioManagerV2:
    manager = PortfolioManagerV2(
        starting_balance=17000.0,
    )

    manager.add_position(
        position={
            "position_id": "pos-1",
            "symbol": "NQ",
            "status": "OPEN",
            "direction": "LONG",
            "entry_price": 100.0,
            "current_price": 100.0,
            "quantity": 2.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "point_value": 2.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
        },
    )

    return manager


def test_accepts_none_portfolio_manager():
    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=None,
    )

    assert (
        monitor.portfolio_manager_v2
        is None
    )


def test_accepts_valid_portfolio_manager():
    lifecycle = FakeTradeLifecycleService()
    manager = build_portfolio_manager()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=manager,
    )

    assert (
        monitor.portfolio_manager_v2
        is manager
    )


def test_rejects_invalid_portfolio_manager():
    lifecycle = FakeTradeLifecycleService()

    with pytest.raises(
        TypeError,
        match="portfolio_manager_v2",
    ):
        LivePositionMonitorV2(
            trade_lifecycle_service=lifecycle,
            portfolio_manager_v2=object(),
        )


def test_updates_portfolio_position_price():
    lifecycle = FakeTradeLifecycleService()
    manager = build_portfolio_manager()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=manager,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert result["processed"] is True

    positions = (
        manager.get_open_positions()
    )

    assert len(positions) == 1

    assert (
        positions[0][
            "current_price"
        ]
        == 105.0
    )

    assert (
        manager.get_total_unrealized_pnl()
        == 20.0
    )


def test_closes_portfolio_position():
    lifecycle = FakeTradeLifecycleService()
    manager = build_portfolio_manager()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=manager,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=110.0,
    )

    assert result["closed_positions"] == 1

    assert (
        manager.get_open_positions()
        == []
    )

    closed = (
        manager.get_closed_positions()
    )

    assert len(closed) == 1

    assert (
        closed[0][
            "realized_pnl"
        ]
        == 40.0
    )

    assert (
        manager.get_available_balance()
        == 17040.0
    )


def test_returns_portfolio_summary():
    lifecycle = FakeTradeLifecycleService()
    manager = build_portfolio_manager()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=manager,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert (
        result["portfolio_summary"][
            "open_positions"
        ]
        == 1
    )

    assert (
        result["portfolio_summary"][
            "total_unrealized_pnl"
        ]
        == 20.0
    )


def test_without_portfolio_manager_returns_none_summary():
    lifecycle = FakeTradeLifecycleService()

    monitor = LivePositionMonitorV2(
        trade_lifecycle_service=lifecycle,
        portfolio_manager_v2=None,
    )

    result = monitor.process_price(
        symbol="NQ",
        current_price=105.0,
    )

    assert (
        result["portfolio_summary"]
        is None
    )
