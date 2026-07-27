import pytest

from backend.dashboard.widgets.performance_overview_widget_v2 import (
    PerformanceOverviewWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "performance_overview": {
                "total_trades": 25,
                "win_rate": 64.0,
                "profit_factor": 2.1,
                "expectancy": 42.5,
                "net_profit": 1250.0,
            },
        }


def build_widget(
    service=None,
):
    return PerformanceOverviewWidgetV2(
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
        == "performance_overview"
    )
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_performance_overview_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert (
        result["widget"]
        == "performance_overview"
    )
    assert result["status"] == "READY"

    data = result["data"]

    assert data["total_trades"] == 25
    assert data["win_rate"] == 64.0
    assert data["profit_factor"] == 2.1
    assert data["expectancy"] == 42.5
    assert data["net_profit"] == 1250.0


def test_returns_empty_when_snapshot_has_no_performance():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "performance_overview": None,
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
