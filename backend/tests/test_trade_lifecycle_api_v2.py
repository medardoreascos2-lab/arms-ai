from fastapi.testclient import TestClient

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
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.api.trade_lifecycle_api_v2 import (
    create_trade_lifecycle_router_v2,
)
from fastapi import FastAPI


def build_service() -> TradeLifecycleServiceV2:
    return TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=20,
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
        starting_balance=17000.0,
    )


def build_client() -> TestClient:
    app = FastAPI()

    app.include_router(
        create_trade_lifecycle_router_v2(
            service=build_service(),
        )
    )

    return TestClient(
        app
    )


def build_valid_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


def test_gets_empty_active_positions():
    client = build_client()

    response = client.get(
        "/v2/positions"
    )

    assert response.status_code == 200

    assert response.json() == {
        "positions": [],
        "count": 0,
    }


def test_submits_trade_signal():
    client = build_client()

    response = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["accepted"] is True

    assert (
        result["prepared_order"][
            "status"
        ]
        == "READY_TO_SUBMIT"
    )

    assert (
        result["execution"][
            "status"
        ]
        == "FILLED"
    )

    assert (
        result["position"][
            "status"
        ]
        == "OPEN"
    )


def test_gets_active_position_after_submit():
    client = build_client()

    client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    )

    response = client.get(
        "/v2/positions"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["count"] == 1
    assert len(result["positions"]) == 1
    assert (
        result["positions"][0][
            "symbol"
        ]
        == "NQ"
    )


def test_updates_position():
    client = build_client()

    submitted = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    ).json()

    position_id = submitted[
        "active_position_id"
    ]

    response = client.post(
        f"/v2/positions/{position_id}/update",
        json={
            "current_price": 105.25,
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["updated"] is True

    assert (
        result["position"][
            "current_price"
        ]
        == 105.25
    )

    assert (
        result["position"][
            "status"
        ]
        == "OPEN"
    )


def test_closes_position_and_returns_history():
    client = build_client()

    submitted = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    ).json()

    position_id = submitted[
        "active_position_id"
    ]

    response = client.post(
        f"/v2/positions/{position_id}/update",
        json={
            "current_price": 110.0,
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert (
        result["position"][
            "status"
        ]
        == "CLOSED"
    )

    history_response = client.get(
        "/v2/trades/history"
    )

    assert history_response.status_code == 200

    history = history_response.json()

    assert history["count"] == 1
    assert history["trades"][0]["result"] == "WIN"


def test_gets_performance_metrics():
    client = build_client()

    response = client.get(
        "/v2/performance"
    )

    assert response.status_code == 200

    metrics = response.json()

    assert metrics["total_trades"] == 0
    assert metrics["starting_balance"] == 17000.0
    assert metrics["ending_balance"] == 17000.0


def test_rejects_second_open_position():
    client = build_client()

    first = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    )

    second = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 409

    assert (
        second.json()["detail"]
        == "position_already_open"
    )


def test_rejects_unknown_position():
    client = build_client()

    response = client.post(
        "/v2/positions/missing/update",
        json={
            "current_price": 105.0,
        },
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]
        == "position_id no existe."
    )


def test_rejects_invalid_current_price():
    client = build_client()

    submitted = client.post(
        "/v2/trades/submit",
        json={
            "signal": build_valid_signal(),
            "order_type": "MARKET",
        },
    ).json()

    position_id = submitted[
        "active_position_id"
    ]

    response = client.post(
        f"/v2/positions/{position_id}/update",
        json={
            "current_price": 0.0,
        },
    )

    assert response.status_code == 422


def test_filters_history_by_symbol():
    client = build_client()

    response = client.get(
        "/v2/trades/history",
        params={
            "symbol": "NQ",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "trades": [],
        "count": 0,
    }
