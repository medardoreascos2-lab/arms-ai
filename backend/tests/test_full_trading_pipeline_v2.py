
from backend.api.app import create_app

from fastapi.testclient import TestClient



def test_dashboard_does_not_start_trading_pipeline():


    app = create_app(
        load_default_strategies=True
    )


    client = TestClient(
        app
    )


    response = client.get(
        "/api/v2/backtesting/dashboard"
    )


    assert (
        response.status_code
        ==
        200
    )


    payload = response.json()

    for field in (
        "strategy_selection", "strategy_decision", "trade_plan",
        "risk_validation", "execution",
    ):
        assert payload[field] is None
