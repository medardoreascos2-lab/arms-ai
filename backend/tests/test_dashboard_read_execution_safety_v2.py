"""No-trade invariants against the wired application and its real PAPER state."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.connectors.paper_broker_connector_v2 import PaperBrokerConnectorV2
from backend.tests.test_dashboard_execution_pipeline_read_only_v3 import URL


def seed_existing_activity(app):
    """Explicit test setup only; the measured read phase starts afterwards."""
    service = app.state.trade_lifecycle_service_v2
    broker = service.broker_connector_v2
    assert isinstance(broker, PaperBrokerConnectorV2)
    execution = broker.submit_order(prepared_order={
        "approved": True, "execution_mode": "PAPER", "decision": "SUBMIT_ORDER",
        "symbol": "MES", "side": "SELL", "order_type": "MARKET", "quantity": 1,
        "entry_price": 5100.0, "stop_loss": 5110.0, "take_profit": 5080.0,
    })
    assert execution["status"] == "FILLED"
    position = service.position_manager.open_position(execution=execution)
    assert position["opened"] is True
    service.restore_active_position(position=position)
    app.state.portfolio_manager_v2.add_position(position=position)
    app.state.trade_journal_v2.record_open_trade({
        **position, "trade_id": "existing-test-journal",
    })
    protection = service.protective_order_registry_v2.create_protection(
        position_id=position["position_id"], symbol=position["symbol"],
        direction=position["direction"], quantity=position["quantity"],
        entry_price=position["entry_price"], stop_price=position["stop_loss"],
        take_profit_price=position["take_profit"],
    )
    service.oco_manager_v2.create_group(
        position_id=position["position_id"], stop_order_id=protection["stop_order_id"],
        take_profit_order_id=protection["take_profit_order_id"],
    )
    app.state.dashboard_trade_event_publisher_v2.publish_trade_opened(trade=position)


def capture(app):
    service = app.state.trade_lifecycle_service_v2
    broker = service.broker_connector_v2
    portfolio = app.state.portfolio_manager_v2
    return deepcopy({
        "orders": broker.get_orders(), "fills": broker.get_fills(),
        "broker_positions": broker.get_positions(),
        "positions": service.get_active_positions(),
        "protections": service.protective_order_registry_v2.list_protections(),
        "oco": service.oco_manager_v2.list_groups(),
        "portfolio_open": portfolio.get_open_positions(),
        "portfolio_closed": portfolio.get_closed_positions(),
        "portfolio": portfolio.get_summary(),
        "balance": portfolio.get_available_balance(),
        "account": app.state.account_state_manager_v2.get_state(),
        "journal": app.state.trade_journal_v2.get_trades(),
        "events": app.state.dashboard_event_bus_v2.get_event_history(),
        "risk_events": app.state.risk_event_store_v2.get_events(),
    })


def forbid_mutations(app, monkeypatch):
    service = app.state.trade_lifecycle_service_v2
    targets = [
        (service, ["submit_signal", "update_position", "replace_active_position",
                   "restore_active_position"]),
        (service.execution_manager, ["prepare_order"]),
        (service.broker_connector_v2, ["submit_order", "modify_order", "cancel_order",
                                      "close_partial", "close_position"]),
        (service.broker_connector_v2.execution_engine, ["execute"]),
        (service.position_manager, ["open_position", "update_position"]),
        (service.protective_order_registry_v2, ["create_protection", "complete_protection",
                                               "cancel_protection", "remove_protection"]),
        (service.oco_manager_v2, ["create_group", "cancel_remaining", "cancel_group",
                                  "remove_group"]),
        (app.state.portfolio_manager_v2, ["add_position", "update_position",
                                         "reduce_position", "close_position"]),
        (app.state.account_state_manager_v2, ["update_from_portfolio", "update_open_risk",
                                             "record_daily_pnl", "reset_daily_state"]),
        (app.state.trade_journal_v2, ["record", "record_open_trade", "close_trade"]),
        (app.state.dashboard_trade_event_publisher_v2,
         ["publish_trade_opened", "publish_trade_closed", "publish_position_updated",
          "publish_portfolio_updated", "publish_risk_updated"]),
        (app.state.dashboard_event_bus_v2, ["publish"]),
    ]
    guards = []
    for target, methods in targets:
        for method in methods:
            guard = Mock(side_effect=AssertionError(f"Read invoked {method}"))
            monkeypatch.setattr(target, method, guard)
            guards.append(guard)
    return guards


@pytest.mark.parametrize("activity", [False, True], ids=["empty", "existing"])
@pytest.mark.parametrize("source_state", ["available", "missing_journal", "incomplete_position"])
def test_repeated_and_concurrent_gets_have_zero_execution_effects(
    tmp_path, monkeypatch, activity, source_state,
):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    if activity:
        seed_existing_activity(app)
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    # Alter only the read projection for partial/unavailable-data scenarios.
    with monkeypatch.context() as reads:
        if source_state == "missing_journal":
            reads.delattr(app.state, "trade_journal_v2")
        elif source_state == "incomplete_position":
            reads.setattr(app.state.trade_lifecycle_service_v2, "get_active_positions",
                          lambda: [{"accepted": True, "symbol": "MES"}])
        client = TestClient(app)  # No background workers or external server.
        first = client.get(URL)
        assert first.status_code == 200
        expected_status = ("AVAILABLE" if activity else "IDLE")
        if source_state != "available":
            expected_status = "UNAVAILABLE"
        assert first.json()["status"] == expected_status
        for _ in range(5):
            response = client.get(URL)
            assert response.status_code == 200
            assert response.json() == first.json()
        barrier = Barrier(8)

        def concurrent_read(_):
            barrier.wait(timeout=10)
            response = client.get(URL)
            assert response.status_code == 200
            return response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(concurrent_read, range(8)))
        assert all(response == first.json() for response in responses)
        client.close()
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()


# All reads in loadDashboard(), plus its analytical POST, exercised together.
DASHBOARD_READS = [
    "/api/v2/dashboard/live", "/api/v2/dashboard/widgets",
    "/api/v2/dashboard/strategy-ranking", "/api/v2/backtesting/dashboard",
    "/api/v2/dashboard/trade-setup", "/api/v2/dashboard/execution-approval",
    "/api/v2/dashboard/execution-simulator", "/api/v2/dashboard/execution-manager",
    "/api/v2/dashboard/performance-intelligence", "/api/v2/dashboard/ai-pattern",
    "/api/v2/dashboard/ai-learning", "/api/v2/dashboard/trading-memory",
    "/api/v2/dashboard/ai-decision-memory", "/api/v2/dashboard/confidence-fusion",
    "/api/v3/dashboard/intelligence-decision", URL, "/api/v2/learning/summary",
    "/api/v2/dashboard/risk", "/api/v2/dashboard/account",
]


@pytest.mark.parametrize("activity", [False, True], ids=["empty", "existing"])
def test_dashboard_load_refresh_and_subscription_do_not_trade(tmp_path, monkeypatch, activity):
    app = create_app(risk_event_store_path_v2=tmp_path / "risk-events.json")
    if activity:
        seed_existing_activity(app)
    before = capture(app)
    guards = forbid_mutations(app, monkeypatch)
    client = TestClient(app)
    with client.websocket_connect("/api/v2/dashboard/ws") as websocket:
        assert websocket.receive_json()["event_type"] == "dashboard_snapshot"
        for _ in range(2):  # Initial load and manual refresh.
            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(client.get, DASHBOARD_READS))
            for path, response in zip(DASHBOARD_READS, responses):
                assert response.status_code == 200, (path, response.text)
            response = client.post("/ai/decision", json={
                "weights": {"trend": 0.3, "risk": 0.3, "performance": 0.4},
                "metrics": {"beta": 1.1, "sharpe_ratio": 1.8,
                            "volatility": 0.15, "drawdown": 0.05},
            })
            assert response.status_code == 200
    client.close()
    assert capture(app) == before
    for guard in guards:
        guard.assert_not_called()
