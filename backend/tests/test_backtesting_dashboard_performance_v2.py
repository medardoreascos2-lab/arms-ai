
from fastapi.testclient import TestClient

from backend.api.app import create_app



def test_dashboard_exposes_performance():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    assert response.status_code == 200


    payload = response.json()


    assert (
        payload["performance"]
        is not None
    )


    assert (
        payload["performance"]["total_trades"]
        == 10
    )


    assert (
        payload["performance"]["winning_trades"]
        == 7
    )


    assert (
        payload["performance"]["win_rate"]
        ==
        70.0
    )


    assert (
        payload["performance"]["net_profit"]
        ==
        1250
    )



def test_dashboard_without_performance():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    assert response.status_code == 200


    payload = response.json()


    assert (
        payload["performance"]
        is not None
    )


    assert (
        payload["performance"]["total_trades"]
        ==
        10
    )
