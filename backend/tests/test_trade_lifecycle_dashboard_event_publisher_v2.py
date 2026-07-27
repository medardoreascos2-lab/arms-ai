import pytest

from backend.dashboard.trade_lifecycle_dashboard_event_publisher_v2 import (
    TradeLifecycleDashboardEventPublisherV2,
)


class FakeEventBus:

    def __init__(self):
        self.events = []

    def publish(
        self,
        *,
        event_type,
        payload,
    ):
        self.events.append(
            {
                "event_type": event_type,
                "payload": payload,
            }
        )

        return {
            "published": True,
            "listeners_notified": 1,
            "listener_errors": 0,
        }


def build_publisher(
    event_bus=None,
):
    return TradeLifecycleDashboardEventPublisherV2(
        event_bus_v2=event_bus,
    )


def test_accepts_none_event_bus():
    publisher = build_publisher()

    assert publisher.event_bus_v2 is None


def test_rejects_invalid_event_bus():
    with pytest.raises(
        TypeError,
        match="event_bus_v2",
    ):
        build_publisher(
            object(),
        )


def test_publish_trade_opened():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_trade_opened(
        trade={
            "position_id": "pos-1",
            "symbol": "NQ",
            "direction": "LONG",
            "quantity": 2,
            "entry_price": 22000.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "trade_opened"

    assert len(event_bus.events) == 1

    event = event_bus.events[0]

    assert event["event_type"] == "trade_opened"
    assert event["payload"]["position_id"] == "pos-1"
    assert event["payload"]["symbol"] == "NQ"


def test_publish_trade_closed():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_trade_closed(
        trade={
            "position_id": "pos-1",
            "symbol": "NQ",
            "realized_pnl": 250.0,
            "exit_reason": "TAKE_PROFIT",
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "trade_closed"

    event = event_bus.events[0]

    assert event["payload"]["realized_pnl"] == 250.0
    assert event["payload"]["exit_reason"] == "TAKE_PROFIT"


def test_publish_position_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_position_updated(
        position={
            "position_id": "pos-1",
            "current_price": 22025.0,
            "unrealized_pnl": 100.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "position_updated"

    assert (
        event_bus.events[0]["payload"][
            "unrealized_pnl"
        ]
        == 100.0
    )


def test_publish_portfolio_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_portfolio_updated(
        portfolio={
            "total_realized_pnl": 500.0,
            "total_unrealized_pnl": 100.0,
            "total_pnl": 600.0,
            "account_equity": 17600.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "portfolio_updated"

    assert (
        event_bus.events[0]["payload"][
            "total_pnl"
        ]
        == 600.0
    )


def test_publish_risk_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_risk_updated(
        risk={
            "trading_blocked": True,
            "blocking_reasons": [
                "daily_loss_limit_reached",
            ],
            "drawdown": 3000.0,
            "open_risk": 0.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "risk_updated"

    assert (
        event_bus.events[0]["payload"][
            "trading_blocked"
        ]
        is True
    )


def test_returns_false_without_event_bus():
    publisher = build_publisher()

    result = publisher.publish_trade_closed(
        trade={
            "position_id": "pos-1",
        },
    )

    assert result["published"] is False
    assert result["reason"] == "no_event_bus"
    assert result["event_type"] == "trade_closed"


@pytest.mark.parametrize(
    (
        "method_name",
        "argument_name",
    ),
    [
        (
            "publish_trade_opened",
            "trade",
        ),
        (
            "publish_trade_closed",
            "trade",
        ),
        (
            "publish_position_updated",
            "position",
        ),
        (
            "publish_portfolio_updated",
            "portfolio",
        ),
        (
            "publish_risk_updated",
            "risk",
        ),
    ],
)
def test_rejects_invalid_payloads(
    method_name,
    argument_name,
):
    publisher = build_publisher(
        FakeEventBus(),
    )

    method = getattr(
        publisher,
        method_name,
    )

    with pytest.raises(
        TypeError,
        match=argument_name,
    ):
        method(
            **{
                argument_name: object(),
            }
        )


def test_payload_is_copied_before_publish():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    trade = {
        "position_id": "pos-1",
        "metadata": {
            "strategy": "EMA_PULLBACK",
        },
    }

    publisher.publish_trade_opened(
        trade=trade,
    )

    trade["metadata"]["strategy"] = (
        "MODIFIED"
    )

    assert (
        event_bus.events[0]["payload"][
            "metadata"
        ]["strategy"]
        == "EMA_PULLBACK"
    )
