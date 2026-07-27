import pytest

from backend.dashboard.widgets.portfolio_summary_widget_v2 import (
    PortfolioSummaryWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "portfolio_summary": {
                "starting_balance": 17000.0,
                "open_positions": 2,
                "closed_positions": 8,
                "total_realized_pnl": 1250.0,
                "total_unrealized_pnl": 150.0,
                "total_pnl": 1400.0,
                "account_equity": 18400.0,
            },
        }


def build_widget(
    service=None,
):
    return PortfolioSummaryWidgetV2(
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
        == "portfolio_summary"
    )
    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_portfolio_summary_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert (
        result["widget"]
        == "portfolio_summary"
    )
    assert result["status"] == "READY"

    data = result["data"]

    assert data["starting_balance"] == 17000.0
    assert data["open_positions"] == 2
    assert data["closed_positions"] == 8
    assert data["total_realized_pnl"] == 1250.0
    assert data["total_unrealized_pnl"] == 150.0
    assert data["total_pnl"] == 1400.0
    assert data["account_equity"] == 18400.0


def test_returns_empty_when_snapshot_has_no_portfolio():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "portfolio_summary": None,
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
