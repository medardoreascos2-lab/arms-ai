
from fastapi.testclient import TestClient

from backend.api.app import create_app



def build_strategy():

    return {
        "strategy_id": "STR-001",
        "name": "EMA50 Smart Money",
        "version": "1.0",
        "status": "CERTIFIED",
        "grade": "A",
        "validation_score": 92.0,
        "performance_score": 85.0,
    }



def test_get_strategy_by_id():

    app = create_app()

    registry = (
        app.state
        .strategy_registry_v2
    )


    registry.register(
        build_strategy()
    )


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/strategies/STR-001"
    )


    assert response.status_code == 200


    payload = response.json()


    assert payload["strategy_id"] == (
        "STR-001"
    )



def test_get_unknown_strategy():

    app = create_app()

    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/strategies/UNKNOWN"
    )


    assert response.status_code == 404
