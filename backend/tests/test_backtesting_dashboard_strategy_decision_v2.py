
from fastapi.testclient import TestClient

from backend.api.app import create_app



def test_dashboard_exposes_strategy_decision():


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
        payload["strategy_decision"]
        is not None
    )


    assert (
        payload["strategy_decision"]
        ["decision"]
        ==
        "EXECUTE"
    )


    assert (
        payload["strategy_decision"]
        ["strategy_id"]
        ==
        "STR-001"
    )



def test_dashboard_strategy_decision_structure():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    payload = response.json()


    assert (
        "decision"
        in
        payload["strategy_decision"]
    )
