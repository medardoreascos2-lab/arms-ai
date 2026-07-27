from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.dashboard_widgets_api_v2 import (
    create_dashboard_widgets_router_v2,
)


class FakeWidgetRegistry:

    def render_all(self):
        return {
            "status": "READY",
            "widget_count": 3,
            "widgets": {
                "performance_score": {
                    "widget": "performance_score",
                    "status": "READY",
                    "data": {
                        "score": 92,
                        "grade": "A+",
                    },
                },
                "account_overview": {
                    "widget": "account_overview",
                    "status": "READY",
                    "data": {
                        "balance": 17100.0,
                        "equity": 17150.0,
                    },
                },
                "risk_status": {
                    "widget": "risk_status",
                    "status": "READY",
                    "data": {
                        "trading_blocked": False,
                    },
                },
            },
        }


def build_client(
    *,
    widget_registry=None,
):
    app = FastAPI()

    router = (
        create_dashboard_widgets_router_v2(
            widget_registry_v2=(
                widget_registry
            ),
        )
    )

    app.include_router(
        router
    )

    return TestClient(
        app
    )


def test_get_dashboard_widgets():
    client = build_client(
        widget_registry=(
            FakeWidgetRegistry()
        ),
    )

    response = client.get(
        "/api/v2/dashboard/widgets"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "READY"
    assert payload["widget_count"] == 3

    assert (
        payload["widgets"][
            "performance_score"
        ]["data"]["score"]
        == 92
    )

    assert (
        payload["widgets"][
            "account_overview"
        ]["data"]["equity"]
        == 17150.0
    )


def test_returns_empty_without_registry():
    client = build_client(
        widget_registry=None,
    )

    response = client.get(
        "/api/v2/dashboard/widgets"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "EMPTY"
    assert payload["widget_count"] == 0
    assert payload["widgets"] == {}


def test_rejects_invalid_registry():
    try:
        create_dashboard_widgets_router_v2(
            widget_registry_v2=object(),
        )
    except TypeError as exc:
        assert (
            "widget_registry_v2"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Se esperaba TypeError."
        )


def test_registry_failure_returns_500():
    class FailingRegistry:

        def render_all(self):
            raise RuntimeError(
                "widget failure"
            )

    client = build_client(
        widget_registry=(
            FailingRegistry()
        ),
    )

    response = client.get(
        "/api/v2/dashboard/widgets"
    )

    assert response.status_code == 500

    payload = response.json()

    assert (
        payload["detail"]
        == "dashboard_widgets_render_failed"
    )
