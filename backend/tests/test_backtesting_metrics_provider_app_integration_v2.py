from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_app_registers_metrics_provider():

    app = create_app()

    provider = (
        app.state
        .backtesting_metrics_provider_v2
    )

    assert provider is not None

    assert callable(
        getattr(
            provider,
            "get_metrics",
            None,
        )
    )


def test_metrics_api_uses_registered_provider():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/metrics"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "metrics": {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_profit": 0.0,
            "max_drawdown": 0.0,
        }
    }
