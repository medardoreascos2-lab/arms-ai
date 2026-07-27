import pytest

from backend.dashboard.widgets.risk_status_widget_v2 import (
    RiskStatusWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "risk_status": {
                "trading_blocked": False,
                "blocking_reasons": [],
                "drawdown": 500.0,
                "open_risk": 200.0,
            },
        }


def build_widget(
    service=None,
):
    return RiskStatusWidgetV2(
        dashboard_live_data_service_v2=(
            service
        ),
    )


def test_accepts_none():
    widget = build_widget()

    assert (
        widget.dashboard_live_data_service_v2
        is None
    )


def test_rejects_invalid_service():
    with pytest.raises(
        TypeError,
        match="dashboard_live_data_service_v2",
    ):
        build_widget(
            object(),
        )


def test_returns_empty_widget():
    widget = build_widget()

    result = widget.render()

    assert result["widget"] == "risk_status"
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_risk_status_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert result["widget"] == "risk_status"
    assert result["status"] == "READY"

    data = result["data"]

    assert data["trading_blocked"] is False
    assert data["blocking_reasons"] == []
    assert data["drawdown"] == 500.0
    assert data["open_risk"] == 200.0


def test_returns_blocked_status():
    class BlockedDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "BLOCKED",
                "risk_status": {
                    "trading_blocked": True,
                    "blocking_reasons": [
                        "daily_loss_limit_reached",
                    ],
                    "drawdown": 4500.0,
                    "open_risk": 0.0,
                },
            }

    widget = build_widget(
        BlockedDashboardService(),
    )

    result = widget.render()

    assert result["status"] == "BLOCKED"
    assert (
        result["data"]["trading_blocked"]
        is True
    )
    assert (
        "daily_loss_limit_reached"
        in result["data"][
            "blocking_reasons"
        ]
    )


def test_returns_empty_when_snapshot_has_no_risk():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "risk_status": None,
            }

    widget = build_widget(
        EmptyDashboardService(),
    )

    result = widget.render()

    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_rejects_invalid_snapshot():
    class InvalidDashboardService:

        def get_snapshot(self):
            return object()

    widget = build_widget(
        InvalidDashboardService(),
    )

    with pytest.raises(
        TypeError,
        match="get_snapshot",
    ):
        widget.render()
