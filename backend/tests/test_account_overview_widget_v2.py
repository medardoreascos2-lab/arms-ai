import pytest

from backend.dashboard.widgets.account_overview_widget_v2 import (
    AccountOverviewWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "account_overview": {
                "balance": 17100.0,
                "equity": 17150.0,
                "daily_pnl": 250.0,
                "drawdown": 500.0,
                "open_risk": 200.0,
            },
        }


def build_widget(
    service=None,
):
    return AccountOverviewWidgetV2(
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

    assert (
        result["widget"]
        == "account_overview"
    )

    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_account_overview_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert (
        result["widget"]
        == "account_overview"
    )

    assert result["status"] == "READY"

    data = result["data"]

    assert data["balance"] == 17100.0
    assert data["equity"] == 17150.0
    assert data["daily_pnl"] == 250.0
    assert data["drawdown"] == 500.0
    assert data["open_risk"] == 200.0


def test_returns_empty_when_snapshot_has_no_account():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "account_overview": None,
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
