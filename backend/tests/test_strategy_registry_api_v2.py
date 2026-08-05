
from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_strategy_registry_api_lists_strategies():

    app = create_app()

    registry = (
        app.state
        .strategy_registry_v2
    )


    registry.register(
        {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "version": "1.0",
            "status": "CERTIFIED",
            "grade": "A",
            "validation_score": 92.0,
            "performance_score": 85.0,
        }
    )


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/strategies"
    )


    assert response.status_code == 200


    payload = response.json()


    assert len(payload["strategies"]) == 1


    assert payload["strategies"][0]["strategy_id"] == (
        "STR-001"
    )



def test_strategy_registry_api_empty():

    app = create_app()

    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/strategies"
    )


    assert response.status_code == 200


    payload = response.json()


    assert payload["strategies"] == []
