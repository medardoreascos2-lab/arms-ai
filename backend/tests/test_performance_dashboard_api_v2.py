from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.performance_dashboard_api_v2 import (
    create_performance_dashboard_router_v2,
)


class FakeDashboardEngine:

    def build(self):
        return {
            "dashboard_status": "READY",
            "account_state": {
                "balance": 17100.0,
                "equity": 17150.0,
                "daily_pnl": 100.0,
                "drawdown": 50.0,
                "open_risk": 200.0,
                "trading_blocked": False,
                "blocking_reasons": [],
            },
            "portfolio_summary": {
                "open_positions": 1,
                "closed_positions": 3,
                "total_pnl": 150.0,
            },
            "trade_journal_summary": {
                "open_trades": 1,
                "closed_trades": 3,
            },
            "analytics": {
                "total_trades": 3,
                "win_rate": 66.6666666667,
                "profit_factor": 2.0,
                "expectancy": 33.3333333333,
                "net_profit": 100.0,
            },
            "breakdown": {
                "by_symbol": {
                    "NQ": {
                        "total_trades": 3,
                        "net_profit": 100.0,
                    }
                }
            },
            "account_overview": {
                "balance": 17100.0,
                "equity": 17150.0,
                "daily_pnl": 100.0,
                "drawdown": 50.0,
                "open_risk": 200.0,
            },
            "performance_overview": {
                "total_trades": 3,
                "win_rate": 66.6666666667,
                "profit_factor": 2.0,
                "expectancy": 33.3333333333,
                "net_profit": 100.0,
            },
            "risk_status": {
                "trading_blocked": False,
                "blocking_reasons": [],
                "drawdown": 50.0,
                "open_risk": 200.0,
            },
        }


def build_client(
    *,
    dashboard_engine=None,
):
    app = FastAPI()

    router = (
        create_performance_dashboard_router_v2(
            dashboard_engine_v2=(
                dashboard_engine
            ),
        )
    )

    app.include_router(
        router
    )

    return TestClient(
        app
    )


def test_get_dashboard():
    client = build_client(
        dashboard_engine=(
            FakeDashboardEngine()
        ),
    )

    response = client.get(
        "/api/v2/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["dashboard_status"]
        == "READY"
    )

    assert (
        payload["account_overview"][
            "equity"
        ]
        == 17150.0
    )

    assert (
        payload["performance_overview"][
            "profit_factor"
        ]
        == 2.0
    )

    assert (
        payload["breakdown"][
            "by_symbol"
        ]["NQ"]["net_profit"]
        == 100.0
    )


def test_rejects_invalid_dashboard_engine():
    try:
        create_performance_dashboard_router_v2(
            dashboard_engine_v2=object(),
        )
    except TypeError as exc:
        assert (
            "dashboard_engine_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_dashboard_engine_failure_returns_500():
    class FailingDashboardEngine:

        def build(self):
            raise RuntimeError(
                "dashboard failure"
            )

    client = build_client(
        dashboard_engine=(
            FailingDashboardEngine()
        ),
    )

    response = client.get(
        "/api/v2/dashboard"
    )

    assert response.status_code == 500

    payload = response.json()

    assert (
        payload["detail"]
        == "dashboard_build_failed"
    )
