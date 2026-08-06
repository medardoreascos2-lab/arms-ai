
from backend.api.app import create_app

from fastapi.testclient import TestClient



def test_full_trading_pipeline_executes_trade():


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



    assert (
        payload["strategy_selection"]
        is not None
    )


    assert (
        payload["strategy_decision"]
        is not None
    )


    assert (
        payload["trade_plan"]
        is not None
    )


    assert (
        payload["risk_validation"]
        is not None
    )


    assert (
        payload["execution"]
        is not None
    )



    assert (
        payload["strategy_decision"]["decision"]
        ==
        "EXECUTE"
    )


    assert (
        payload["trade_plan"]["status"]
        ==
        "READY"
    )


    assert (
        payload["risk_validation"]["status"]
        ==
        "APPROVED"
    )


    assert (
        payload["execution"]["status"]
        ==
        "EXECUTED"
    )


    assert (
        payload["execution"]["direction"]
        ==
        "BUY"
    )
