
from fastapi.testclient import TestClient

from backend.api.app import create_app



def test_dashboard_strategy_performance_is_unavailable():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    assert response.status_code == 200


    payload = response.json()


    assert payload["strategy_performance"] is None



def test_dashboard_strategy_performance_structure():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    payload = response.json()


    assert payload["strategy_performance"] is None
