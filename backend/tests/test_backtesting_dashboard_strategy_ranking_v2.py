
from fastapi.testclient import TestClient

from backend.api.app import create_app



def test_dashboard_exposes_strategy_ranking():


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
        payload["strategy_ranking"]
        is not None
    )


    assert (
        payload["strategy_ranking"]
        ["ranking"]
        [0]
        ["strategy_id"]
        ==
        "STR-001"
    )



def test_dashboard_strategy_ranking_structure():


    app = create_app()


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    payload = response.json()


    assert (
        "ranking"
        in
        payload["strategy_ranking"]
    )
