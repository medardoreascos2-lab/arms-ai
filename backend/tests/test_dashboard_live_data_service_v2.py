import pytest

from backend.dashboard.dashboard_live_data_service_v2 import (
    DashboardLiveDataServiceV2,
)


class FakeDashboardEngine:

    def build(self):
        return {
            "dashboard_status": "READY",
            "account_overview": {
                "balance": 17100.0,
                "equity": 17150.0,
            },
            "portfolio_summary": {
                "total_pnl": 150.0,
            },
            "performance_overview": {
                "win_rate": 66.6,
            },
            "risk_status": {
                "trading_blocked": False,
            },
            "performance_score": {
                "score": 92,
                "grade": "A+",
            },
            "analytics": {
                "profit_factor": 2.1,
            },
            "breakdown": {
                "by_symbol": {},
            },
        }


def build_service(
    dashboard_engine=None,
):
    return DashboardLiveDataServiceV2(
        dashboard_engine_v2=dashboard_engine,
    )


def test_accepts_none():
    service = build_service()

    assert service.dashboard_engine_v2 is None


def test_rejects_invalid_dashboard_engine():

    with pytest.raises(
        TypeError,
        match="dashboard_engine_v2",
    ):
        build_service(
            object(),
        )


def test_returns_empty_snapshot():

    service = build_service()

    snapshot = service.get_snapshot()

    assert snapshot["dashboard_status"] == "EMPTY"

    assert snapshot["snapshot_time"] is not None


def test_returns_dashboard_snapshot():

    service = build_service(
        FakeDashboardEngine(),
    )

    snapshot = service.get_snapshot()

    assert snapshot["dashboard_status"] == "READY"

    assert snapshot["performance_score"]["score"] == 92

    assert snapshot["portfolio_summary"]["total_pnl"] == 150.0

    assert snapshot["snapshot_time"] is not None
