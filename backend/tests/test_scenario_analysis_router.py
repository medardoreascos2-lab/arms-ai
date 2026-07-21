from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_scenario_analysis_endpoint():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/scenario-analysis",
        json={
            "weights": {
                "AAPL": 0.4,
                "MSFT": 0.35,
                "NVDA": 0.25,
            },
            "scenario": "technology_shock",
            "initial_value": 1000.0,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["scenario"] == (
        "technology_shock"
    )
    assert body["initial_value"] == 1000.0
    assert body["final_value"] < 1000.0
    assert body["absolute_impact"] < 0.0
    assert body["percentage_impact"] < 0.0

    assert set(body["shocks"]) == {
        "AAPL",
        "MSFT",
        "NVDA",
    }

    assert set(body["asset_impacts"]) == {
        "AAPL",
        "MSFT",
        "NVDA",
    }


def test_scenario_analysis_rejects_invalid_weights():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/scenario-analysis",
        json={
            "weights": {
                "AAPL": 0.2,
                "MSFT": 0.2,
            },
            "scenario": "covid_2020",
        },
    )

    assert response.status_code == 400


def test_scenario_analysis_rejects_unknown_scenario():
    client = TestClient(
        create_app()
    )

    response = client.post(
        "/portfolio/scenario-analysis",
        json={
            "weights": {
                "AAPL": 1.0,
            },
            "scenario": "unknown",
        },
    )

    assert response.status_code == 400
