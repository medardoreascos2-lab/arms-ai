from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import create_autospec

from backend.services.trade_lifecycle_service_v2 import TradeLifecycleServiceV2

from backend.api.trade_lifecycle_api_v2 import create_trade_lifecycle_router_v2


class LifecycleSpy:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_signal(
        self,
        *,
        signal,
        order_type,
        risk_context,
    ):
        self.calls.append(
            {
                "signal": signal,
                "order_type": order_type,
                "risk_context": risk_context,
            }
        )

        return {
            "accepted": False,
            "reason": "phase1_route_delegation_probe",
            "prepared_order": None,
            "execution": None,
        }

    def get_active_positions(self):
        return []

    def update_position(
        self,
        *,
        position_id,
        current_price,
    ):
        raise AssertionError(
            "submit route must not call update_position"
        )

    def get_trade_history(
        self,
        *,
        limit=None,
        symbol=None,
    ):
        return []


def build_client():
    service = create_autospec(TradeLifecycleServiceV2, instance=True)
    service.submit_signal.return_value = {
        "accepted": False,
        "reason": "phase1_route_delegation_probe",
        "prepared_order": None,
        "execution": None,
    }

    app = FastAPI()
    app.include_router(
        create_trade_lifecycle_router_v2(service=service)
    )

    return TestClient(app), service


def test_submit_route_delegates_exactly_once_to_lifecycle():
    client, service = build_client()

    payload = {
        "signal": {
            "symbol": "NQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "take_profit": 20100.0,
        },
        "order_type": "MARKET",
        "risk_context": {
            "account_balance": 150000.0,
            "risk_percent": 0.5,
            "point_value": 20.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 20000.0,
        },
    }

    response = client.post(
        "/v2/trades/submit",
        json=payload,
    )

    assert response.status_code == 200
    service.submit_signal.assert_called_once_with(
        signal=payload["signal"],
        order_type=payload["order_type"],
        risk_context=payload["risk_context"],
    )

    body = response.json()

    assert body["accepted"] is False
    assert (
        body["reason"]
        == "phase1_route_delegation_probe"
    )


def test_submit_route_returns_lifecycle_result_without_parallel_execution():
    client, service = build_client()

    payload = {
        "signal": {
            "symbol": "NQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "take_profit": 20100.0,
        },
        "order_type": "MARKET",
        "risk_context": {
            "account_balance": 150000.0,
            "risk_percent": 0.5,
            "point_value": 20.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 20000.0,
        },
    }

    response = client.post(
        "/v2/trades/submit",
        json=payload,
    )

    assert response.status_code == 200
    assert service.submit_signal.call_count == 1

    assert response.json() == {
        "accepted": False,
        "reason": "phase1_route_delegation_probe",
        "prepared_order": None,
        "execution": None,
    }
