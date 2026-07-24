from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


EXPECTED_ROUTES = {
    "/v2/positions",
    "/v2/trades/submit",
    "/v2/positions/{position_id}/update",
    "/v2/trades/history",
    "/v2/performance",
}


def test_create_app_registers_trade_lifecycle_service_v2():
    app = create_app()

    assert hasattr(
        app.state,
        "trade_lifecycle_service_v2",
    )

    assert isinstance(
        app.state.trade_lifecycle_service_v2,
        TradeLifecycleServiceV2,
    )



def test_create_app_registers_trade_lifecycle_routes_v2():
    client = TestClient(
        create_app()
    )

    endpoints = [
        (
            "GET",
            "/v2/positions",
            None,
            200,
        ),
        (
            "GET",
            "/v2/performance",
            None,
            200,
        ),
        (
            "GET",
            "/v2/trades/history",
            None,
            200,
        ),
    ]

    for (
        method,
        url,
        payload,
        expected,
    ) in endpoints:

        if method == "GET":
            response = client.get(
                url
            )
        else:
            response = client.post(
                url,
                json=payload,
            )

        assert (
            response.status_code
            == expected
        )


def test_main_app_trade_lifecycle_api_flow():
    app = create_app()
    client = TestClient(
        app
    )

    positions_response = client.get(
        "/v2/positions"
    )

    assert positions_response.status_code == 200

    assert positions_response.json() == {
        "positions": [],
        "count": 0,
    }

    performance_response = client.get(
        "/v2/performance"
    )

    assert performance_response.status_code == 200

    metrics = performance_response.json()

    assert metrics["total_trades"] == 0
    assert metrics["starting_balance"] == 17000.0
    assert metrics["ending_balance"] == 17000.0


def test_create_app_uses_injected_trade_lifecycle_service_v2():
    from backend.analytics.performance_analytics_v2 import (
        PerformanceAnalyticsV2,
    )
    from backend.analytics.trade_history_manager_v2 import (
        TradeHistoryManagerV2,
    )
    from backend.execution.execution_manager_v2 import (
        ExecutionManagerV2,
    )
    from backend.execution.paper_execution_engine_v2 import (
        PaperExecutionEngineV2,
    )
    from backend.execution.position_manager_v2 import (
        PositionManagerV2,
    )

    service = TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=5,
            )
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        position_manager=(
            PositionManagerV2(
                point_value=2.0,
            )
        ),
        trade_history_manager=(
            TradeHistoryManagerV2()
        ),
        performance_analytics=(
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
        ),
        starting_balance=25000.0,
    )

    app = create_app(
        trade_lifecycle_service_v2=service,
    )

    assert (
        app.state.trade_lifecycle_service_v2
        is service
    )

    client = TestClient(
        app
    )

    response = client.get(
        "/v2/performance"
    )

    assert response.status_code == 200

    assert (
        response.json()[
            "starting_balance"
        ]
        == 25000.0
    )


def test_create_app_rejects_invalid_trade_lifecycle_service_v2():
    import pytest

    with pytest.raises(
        TypeError,
        match="trade_lifecycle_service_v2",
    ):
        create_app(
            trade_lifecycle_service_v2=object(),
        )
