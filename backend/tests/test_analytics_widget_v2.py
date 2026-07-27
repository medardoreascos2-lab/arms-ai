import pytest

from backend.dashboard.widgets.analytics_widget_v2 import (
    AnalyticsWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "analytics": {
                "total_trades": 25,
                "winning_trades": 16,
                "losing_trades": 8,
                "breakeven_trades": 1,
                "gross_profit": 3200.0,
                "gross_loss": 1400.0,
                "net_profit": 1800.0,
                "average_win": 200.0,
                "average_loss": 175.0,
                "largest_win": 500.0,
                "largest_loss": -350.0,
                "win_rate": 64.0,
                "profit_factor": 2.2857142857,
                "expectancy": 72.0,
                "average_duration_seconds": 420.0,
            },
        }


def build_widget(
    service=None,
):
    return AnalyticsWidgetV2(
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

    assert result["widget"] == "analytics"
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_analytics_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert result["widget"] == "analytics"
    assert result["status"] == "READY"

    data = result["data"]

    assert data["total_trades"] == 25
    assert data["winning_trades"] == 16
    assert data["losing_trades"] == 8
    assert data["breakeven_trades"] == 1
    assert data["gross_profit"] == 3200.0
    assert data["gross_loss"] == 1400.0
    assert data["net_profit"] == 1800.0
    assert data["profit_factor"] == pytest.approx(
        2.2857142857
    )
    assert data["expectancy"] == 72.0


def test_returns_empty_when_snapshot_has_no_analytics():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "analytics": None,
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
