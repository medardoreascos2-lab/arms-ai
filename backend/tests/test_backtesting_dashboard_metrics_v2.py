from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_dashboard_exposes_backtesting_metrics():

    app = create_app()

    provider = (
        app.state
        .backtesting_metrics_provider_v2
    )

    provider.add_trade(
        {
            "pnl": 500,
        }
    )

    provider.add_trade(
        {
            "pnl": -100,
        }
    )

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["metrics"] == (
        provider.get_metrics()
    )


def test_dashboard_metrics_empty():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    assert response.json()["metrics"] is None
