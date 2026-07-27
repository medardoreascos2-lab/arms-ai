import pytest

from backend.dashboard.widgets.performance_score_widget_v2 import (
    PerformanceScoreWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "performance_score": {
                "score": 92,
                "grade": "A+",
                "status": "EXCELLENT",
                "recommendation": "CONTINUE_TRADING",
                "penalties": [],
                "score_breakdown": {
                    "win_rate_score": 28,
                    "profit_factor_score": 29,
                    "expectancy_score": 18,
                    "drawdown_score": 12,
                    "daily_pnl_score": 5,
                },
            },
        }


def build_widget(service=None):
    return PerformanceScoreWidgetV2(
        dashboard_live_data_service_v2=service,
    )


def test_accepts_none():
    widget = build_widget()

    assert widget.dashboard_live_data_service_v2 is None


def test_rejects_invalid_service():
    with pytest.raises(
        TypeError,
        match="dashboard_live_data_service_v2",
    ):
        build_widget(object())


def test_returns_empty_widget():
    widget = build_widget()

    result = widget.render()

    assert result["widget"] == "performance_score"
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_score_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert result["widget"] == "performance_score"
    assert result["status"] == "READY"
    assert result["data"]["score"] == 92
    assert result["data"]["grade"] == "A+"
    assert result["data"]["recommendation"] == "CONTINUE_TRADING"
