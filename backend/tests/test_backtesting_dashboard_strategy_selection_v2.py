
from fastapi.testclient import TestClient

from backend.api.app import create_app



def test_dashboard_exposes_strategy_selection():


    app = create_app(load_default_strategies=True)


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    assert response.status_code == 200


    payload = response.json()


    assert (
        payload["strategy_selection"]
        is not None
    )


    assert (
        payload["strategy_selection"]
        ["strategy_id"]
        ==
        "STR-001"
    )
