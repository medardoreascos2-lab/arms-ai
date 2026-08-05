from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_dashboard_exposes_performance_report():

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

    assert payload["performance_report"] == {
        "score": 55,
        "rating": "WARNING",
        "metrics": provider.get_metrics(),
    }


def test_dashboard_performance_report_exists_empty():

    app = create_app()

    client = TestClient(app)

    response = client.get(
        "/api/v2/backtesting/dashboard"
    )

    assert response.status_code == 200

    report = (
        response.json()
        ["performance_report"]
    )

    assert "score" in report
    assert "rating" in report
    assert "metrics" in report
