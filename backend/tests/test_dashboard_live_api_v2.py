from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dashboard_live_api_v2 import (
    create_dashboard_live_router_v2,
)


class FakeLiveDataService:

    def get_snapshot(self):
        return {
            "snapshot_time": (
                "2026-07-25T23:30:00+00:00"
            ),
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
                "status": "EXCELLENT",
                "recommendation": (
                    "CONTINUE_TRADING"
                ),
            },
            "analytics": {
                "profit_factor": 2.1,
            },
            "breakdown": {
                "by_symbol": {},
            },
        }


def build_client(
    *,
    live_data_service=None,
):
    app = FastAPI()

    router = (
        create_dashboard_live_router_v2(
            live_data_service_v2=(
                live_data_service
            ),
        )
    )

    app.include_router(
        router
    )

    return TestClient(
        app
    )


def test_get_live_dashboard_snapshot():
    client = build_client(
        live_data_service=(
            FakeLiveDataService()
        ),
    )

    response = client.get(
        "/api/v2/dashboard/live"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["dashboard_status"]
        == "READY"
    )

    assert (
        payload["snapshot_time"]
        == "2026-07-25T23:30:00+00:00"
    )

    assert (
        payload["performance_score"][
            "score"
        ]
        == 92
    )

    assert (
        payload["account_overview"][
            "equity"
        ]
        == 17150.0
    )


def test_returns_empty_snapshot_without_service():
    client = build_client(
        live_data_service=None,
    )

    response = client.get(
        "/api/v2/dashboard/live"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["dashboard_status"]
        == "EMPTY"
    )

    assert (
        payload["snapshot_time"]
        is not None
    )


def test_rejects_invalid_live_data_service():
    try:
        create_dashboard_live_router_v2(
            live_data_service_v2=object(),
        )
    except TypeError as exc:
        assert (
            "live_data_service_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_live_data_service_failure_returns_500():
    class FailingLiveDataService:

        def get_snapshot(self):
            raise RuntimeError(
                "snapshot failure"
            )

    client = build_client(
        live_data_service=(
            FailingLiveDataService()
        ),
    )

    response = client.get(
        "/api/v2/dashboard/live"
    )

    assert response.status_code == 500

    payload = response.json()

    assert (
        payload["detail"]
        == "dashboard_live_snapshot_failed"
    )
