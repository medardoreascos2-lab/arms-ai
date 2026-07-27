import pytest

from backend.dashboard.widgets.breakdown_widget_v2 import (
    BreakdownWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "breakdown": {
                "by_symbol": {
                    "NQ": {
                        "total_trades": 10,
                        "winning_trades": 7,
                        "losing_trades": 3,
                        "net_profit": 1200.0,
                        "win_rate": 70.0,
                    },
                },
                "by_direction": {
                    "LONG": {
                        "total_trades": 6,
                        "net_profit": 900.0,
                    },
                    "SHORT": {
                        "total_trades": 4,
                        "net_profit": 300.0,
                    },
                },
                "by_session": {
                    "ASIA": {
                        "total_trades": 4,
                        "net_profit": 350.0,
                    },
                    "NEW_YORK": {
                        "total_trades": 6,
                        "net_profit": 850.0,
                    },
                },
                "by_strategy": {
                    "EMA_PULLBACK": {
                        "total_trades": 7,
                        "net_profit": 950.0,
                    },
                },
                "by_timeframe": {
                    "5M": {
                        "total_trades": 8,
                        "net_profit": 1050.0,
                    },
                },
                "by_exit_reason": {
                    "TAKE_PROFIT": {
                        "total_trades": 7,
                        "net_profit": 1800.0,
                    },
                    "STOP_LOSS": {
                        "total_trades": 3,
                        "net_profit": -600.0,
                    },
                },
            },
        }


def build_widget(
    service=None,
):
    return BreakdownWidgetV2(
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

    assert result["widget"] == "breakdown"
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_breakdown_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert result["widget"] == "breakdown"
    assert result["status"] == "READY"

    data = result["data"]

    assert (
        data["by_symbol"]["NQ"][
            "net_profit"
        ]
        == 1200.0
    )

    assert (
        data["by_direction"]["LONG"][
            "net_profit"
        ]
        == 900.0
    )

    assert (
        data["by_session"]["NEW_YORK"][
            "net_profit"
        ]
        == 850.0
    )

    assert (
        data["by_strategy"]["EMA_PULLBACK"][
            "total_trades"
        ]
        == 7
    )

    assert (
        data["by_timeframe"]["5M"][
            "net_profit"
        ]
        == 1050.0
    )

    assert (
        data["by_exit_reason"]["STOP_LOSS"][
            "net_profit"
        ]
        == -600.0
    )


def test_returns_empty_when_snapshot_has_no_breakdown():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "breakdown": None,
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
