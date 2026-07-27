import pytest

from backend.dashboard.widgets.trade_journal_summary_widget_v2 import (
    TradeJournalSummaryWidgetV2,
)


class FakeDashboardService:

    def get_snapshot(self):
        return {
            "dashboard_status": "READY",
            "trade_journal_summary": {
                "open_trades": 1,
                "closed_trades": 12,
                "winning_trades": 8,
                "losing_trades": 4,
                "total_realized_pnl": 1450.0,
                "win_rate": 66.6666666667,
            },
        }


def build_widget(
    service=None,
):
    return TradeJournalSummaryWidgetV2(
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
        == "trade_journal_summary"
    )

    assert result["status"] == "EMPTY"
    assert result["data"] is None


def test_returns_trade_journal_summary_widget():
    widget = build_widget(
        FakeDashboardService(),
    )

    result = widget.render()

    assert (
        result["widget"]
        == "trade_journal_summary"
    )

    assert result["status"] == "READY"

    data = result["data"]

    assert data["open_trades"] == 1
    assert data["closed_trades"] == 12
    assert data["winning_trades"] == 8
    assert data["losing_trades"] == 4
    assert data["total_realized_pnl"] == 1450.0
    assert data["win_rate"] == pytest.approx(
        66.6666666667
    )


def test_returns_empty_when_snapshot_has_no_journal():
    class EmptyDashboardService:

        def get_snapshot(self):
            return {
                "dashboard_status": "EMPTY",
                "trade_journal_summary": None,
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
