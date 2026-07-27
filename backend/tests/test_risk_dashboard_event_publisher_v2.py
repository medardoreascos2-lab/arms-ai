import pytest

from backend.dashboard.risk_dashboard_event_publisher_v2 import (
    RiskDashboardEventPublisherV2,
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
    return RiskDashboardEventPublisherV2(
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


def test_publish_risk_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_risk_updated(
        risk={
            "approved": False,
            "trading_blocked": True,
            "blocking_reasons": [
                "daily_loss_limit_reached",
            ],
            "daily_loss_used": 3000.0,
            "total_drawdown": 4200.0,
            "current_total_open_risk": 0.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "risk_updated"

    assert len(event_bus.events) == 1

    event = event_bus.events[0]

    assert event["event_type"] == "risk_updated"

    assert (
        event["payload"]["trading_blocked"]
        is True
    )

    assert (
        "daily_loss_limit_reached"
        in event["payload"][
            "blocking_reasons"
        ]
    )


def test_publish_daily_loss_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_daily_loss_updated(
        daily_loss={
            "daily_loss_used": 1500.0,
            "maximum_daily_loss": 3000.0,
            "remaining_daily_loss_capacity": 1500.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "risk_updated"

    payload = event_bus.events[0]["payload"]

    assert (
        payload["risk_update_type"]
        == "daily_loss"
    )

    assert payload["daily_loss_used"] == 1500.0


def test_publish_drawdown_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_drawdown_updated(
        drawdown={
            "total_drawdown": 2000.0,
            "maximum_total_drawdown": 4500.0,
            "remaining_drawdown_capacity": 2500.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "risk_updated"

    payload = event_bus.events[0]["payload"]

    assert (
        payload["risk_update_type"]
        == "drawdown"
    )

    assert payload["total_drawdown"] == 2000.0


def test_publish_open_risk_updated():
    event_bus = FakeEventBus()

    publisher = build_publisher(
        event_bus,
    )

    result = publisher.publish_open_risk_updated(
        open_risk={
            "current_total_open_risk": 500.0,
            "projected_total_open_risk": 750.0,
            "maximum_total_open_risk": 1500.0,
        },
    )

    assert result["published"] is True
    assert result["event_type"] == "risk_updated"

    payload = event_bus.events[0]["payload"]

    assert (
        payload["risk_update_type"]
        == "open_risk"
    )

    assert (
        payload["current_total_open_risk"]
        == 500.0
    )


def test_returns_false_without_event_bus():
    publisher = build_publisher()

    result = publisher.publish_risk_updated(
        risk={
            "trading_blocked": False,
        },
    )

    assert result["published"] is False
    assert result["reason"] == "no_event_bus"
    assert result["event_type"] == "risk_updated"


@pytest.mark.parametrize(
    (
        "method_name",
        "argument_name",
    ),
    [
        (
            "publish_risk_updated",
            "risk",
        ),
        (
            "publish_daily_loss_updated",
            "daily_loss",
        ),
        (
            "publish_drawdown_updated",
            "drawdown",
        ),
        (
            "publish_open_risk_updated",
            "open_risk",
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

    risk = {
        "blocking_reasons": [
            "daily_loss_limit_reached",
        ],
        "metadata": {
            "source": "RiskManagerV2",
        },
    }

    publisher.publish_risk_updated(
        risk=risk,
    )

    risk["metadata"]["source"] = "MODIFIED"

    assert (
        event_bus.events[0]["payload"][
            "metadata"
        ]["source"]
        == "RiskManagerV2"
    )
