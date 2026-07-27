import pytest

from backend.dashboard.dashboard_refresh_service_v2 import (
    DashboardRefreshServiceV2,
)


class FakeLiveDataService:

    def __init__(self):
        self.calls = 0

    def get_snapshot(self):
        self.calls += 1

        return {
            "snapshot_time": (
                f"2026-07-26T01:00:0{self.calls}+00:00"
            ),
            "dashboard_status": "READY",
            "performance_score": {
                "score": 90 + self.calls,
            },
        }


class FakeWidgetRegistry:

    def __init__(self):
        self.calls = 0

    def render_all(self):
        self.calls += 1

        return {
            "status": "READY",
            "widget_count": 8,
            "widgets": {
                "performance_score": {
                    "widget": "performance_score",
                    "status": "READY",
                    "data": {
                        "score": 90 + self.calls,
                    },
                },
            },
        }


def build_service(
    *,
    live_data_service=None,
    widget_registry=None,
):
    return DashboardRefreshServiceV2(
        live_data_service_v2=(
            live_data_service
        ),
        widget_registry_v2=(
            widget_registry
        ),
    )


def test_accepts_none_dependencies():
    service = build_service()

    assert service.live_data_service_v2 is None
    assert service.widget_registry_v2 is None


def test_rejects_invalid_live_data_service():
    with pytest.raises(
        TypeError,
        match="live_data_service_v2",
    ):
        build_service(
            live_data_service=object(),
        )


def test_rejects_invalid_widget_registry():
    with pytest.raises(
        TypeError,
        match="widget_registry_v2",
    ):
        build_service(
            widget_registry=object(),
        )


def test_starts_without_cached_data():
    service = build_service()

    assert service.get_cached_snapshot() is None
    assert service.get_cached_widgets() is None

    state = service.get_state()

    assert state["refresh_count"] == 0
    assert state["last_refresh_time"] is None
    assert state["last_reason"] is None
    assert state["last_event"] is None


def test_refreshes_snapshot_and_widgets():
    live_data = FakeLiveDataService()
    widget_registry = FakeWidgetRegistry()

    service = build_service(
        live_data_service=live_data,
        widget_registry=widget_registry,
    )

    result = service.refresh(
        reason="trade_closed",
        event={
            "event_type": "trade_closed",
            "payload": {
                "position_id": "pos-1",
            },
        },
    )

    assert result["refreshed"] is True
    assert result["reason"] == "trade_closed"
    assert result["refresh_count"] == 1

    snapshot = service.get_cached_snapshot()
    widgets = service.get_cached_widgets()

    assert snapshot["dashboard_status"] == "READY"
    assert snapshot["performance_score"]["score"] == 91

    assert widgets["widget_count"] == 8
    assert (
        widgets["widgets"][
            "performance_score"
        ]["data"]["score"]
        == 91
    )


def test_refreshes_multiple_times():
    service = build_service(
        live_data_service=FakeLiveDataService(),
        widget_registry=FakeWidgetRegistry(),
    )

    service.refresh(
        reason="trade_opened",
        event={
            "event_type": "trade_opened",
            "payload": {},
        },
    )

    result = service.refresh(
        reason="portfolio_updated",
        event={
            "event_type": "portfolio_updated",
            "payload": {},
        },
    )

    assert result["refresh_count"] == 2

    state = service.get_state()

    assert state["refresh_count"] == 2
    assert state["last_reason"] == "portfolio_updated"
    assert (
        state["last_event"]["event_type"]
        == "portfolio_updated"
    )


def test_refresh_without_dependencies():
    service = build_service()

    result = service.refresh(
        reason="dashboard_refresh",
        event={
            "event_type": "dashboard_refresh",
            "payload": {},
        },
    )

    assert result["refreshed"] is True
    assert result["snapshot_updated"] is False
    assert result["widgets_updated"] is False
    assert result["refresh_count"] == 1


def test_rejects_invalid_reason():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="reason",
    ):
        service.refresh(
            reason="",
            event={},
        )


def test_rejects_invalid_event():
    service = build_service()

    with pytest.raises(
        TypeError,
        match="event",
    ):
        service.refresh(
            reason="trade_closed",
            event=object(),
        )


def test_cached_data_is_a_copy():
    service = build_service(
        live_data_service=FakeLiveDataService(),
        widget_registry=FakeWidgetRegistry(),
    )

    service.refresh(
        reason="trade_closed",
        event={
            "event_type": "trade_closed",
            "payload": {},
        },
    )

    snapshot = service.get_cached_snapshot()
    snapshot["modified"] = True

    widgets = service.get_cached_widgets()
    widgets["modified"] = True

    fresh_snapshot = service.get_cached_snapshot()
    fresh_widgets = service.get_cached_widgets()

    assert "modified" not in fresh_snapshot
    assert "modified" not in fresh_widgets


def test_state_is_a_copy():
    service = build_service()

    state = service.get_state()
    state["refresh_count"] = 999

    fresh_state = service.get_state()

    assert fresh_state["refresh_count"] == 0
