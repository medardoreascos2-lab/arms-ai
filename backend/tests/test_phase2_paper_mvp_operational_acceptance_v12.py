"""V12 operational PAPER MVP acceptance through canonical application owners."""
import pytest
from starlette.websockets import WebSocketDisconnect

from backend.services.runtime_context_v2 import build_runtime_context
from backend.tests.runtime_market_fixture_v81 import publish_test_market
from backend.tests.test_account_runtime_transition_v2 import hosted, target
from backend.tests.test_account_switch_safety_containment_v2 import signal
from backend.tests.test_phase1_consolidated_acceptance_v8 import submission
from backend.tests.test_runtime_admission_v81 import economic_state


def _submit(host):
    response = host.client.post("/v2/trades/submit", json=submission(host))
    assert response.status_code == 200, response.text
    return response.json()


def test_paper_mvp_no_trade_fails_closed_before_market_authority(hosted):
    runtime = hosted.c.published.runtime
    before = economic_state(runtime)

    result = _submit(hosted)

    assert result["accepted"] is False
    assert result.get("prepared_order") is None
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    assert runtime.trade_lifecycle_service.get_active_positions() == []
    assert runtime.trade_lifecycle_service.trade_journal_v2.get_trades() == []
    assert economic_state(runtime) == before


def test_paper_mvp_risk_rejection_has_no_execution_or_financial_mutation(hosted, tmp_path):
    runtime = hosted.c.published.runtime
    publish_test_market(runtime.trade_lifecycle_service, directory=tmp_path)
    runtime.account_state_manager_v2.record_daily_pnl(daily_pnl=-3000.0)
    before = economic_state(runtime)

    result = _submit(hosted)

    assert result["accepted"] is False
    assert result.get("prepared_order") is None
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []
    assert runtime.trade_lifecycle_service.get_active_positions() == []
    assert runtime.trade_lifecycle_service.trade_journal_v2.get_trades() == []
    assert economic_state(runtime) == before


def test_paper_mvp_valid_trade_dashboard_and_close_stay_reconciled(hosted, tmp_path):
    assert hosted.c.phase == "READY"
    runtime = hosted.c.published.runtime
    assert runtime.execution_manager.execution_mode == "PAPER"
    publish_test_market(runtime.trade_lifecycle_service, directory=tmp_path)

    result = _submit(hosted)
    assert result["accepted"] is True, result
    assert len(runtime.trade_lifecycle_service.broker_connector_v2.get_fills()) == 1
    assert len(runtime.trade_lifecycle_service.get_active_positions()) == 1
    assert len(runtime.portfolio_manager_v2.get_open_positions()) == 1
    assert len(runtime.trade_lifecycle_service.trade_journal_v2.get_trades()) == 1

    http_snapshot = hosted.client.get("/api/v2/dashboard/live")
    assert http_snapshot.status_code == 200, http_snapshot.text
    with hosted.client.websocket_connect("/api/v2/dashboard/ws") as socket:
        ws_event = socket.receive_json()
    assert ws_event["event_type"] == "dashboard_snapshot"
    ws_snapshot = ws_event["data"]
    assert ws_snapshot["runtime"]["account_id"] == runtime.execution_state_store.account_identity["account_id"]
    assert len(ws_snapshot["positions"]) == 1

    position_id = result["position"]["position_id"]
    runtime.trade_lifecycle_service.update_position(
        position_id=position_id,
        current_price=10010.0,
    )
    assert runtime.trade_lifecycle_service.get_active_positions() == []
    assert len(runtime.portfolio_manager_v2.get_open_positions()) == 0
    assert runtime.account_state_manager_v2.get_state()["realized_pnl"] > 0
    assert len(runtime.trade_lifecycle_service.trade_journal_v2.get_trades()) == 1

    duplicate = _submit(hosted)
    assert duplicate["accepted"] is False
    assert len(runtime.trade_lifecycle_service.broker_connector_v2.get_fills()) == 1
    assert len(runtime.trade_lifecycle_service.trade_journal_v2.get_trades()) == 1


def test_paper_mvp_account_switch_retires_socket_and_clears_projection(hosted, tmp_path):
    runtime = hosted.c.published.runtime
    publish_test_market(runtime.trade_lifecycle_service, directory=tmp_path)
    result = _submit(hosted)
    assert result["accepted"] is True
    runtime.trade_lifecycle_service.update_position(
        position_id=result["position"]["position_id"],
        current_price=10010.0,
    )

    with hosted.client.websocket_connect("/api/v2/dashboard/ws") as socket:
        assert socket.receive_json()["event_type"] == "dashboard_snapshot"
        response = hosted.client.post(
            "/api/v2/dashboard/account-manager/switch",
            json=target(hosted, "B"),
        )
        assert response.status_code == 200, response.text
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()

    current = hosted.c.published.runtime
    assert current.execution_state_store.account_identity["account_id"] != runtime.execution_state_store.account_identity["account_id"]
    assert current.trade_lifecycle_service.get_active_positions() == []
    assert hosted.client.get("/api/v2/dashboard/live").json()["runtime"]["account_id"] == current.execution_state_store.account_identity["account_id"]


def test_paper_mvp_restart_recovers_one_fill_without_resubmission(runtime, tmp_path):
    manager = runtime.safety._managers[0]
    context = build_runtime_context(account_manager=manager)
    context.runtime_lifecycle_manager.start_clean()
    state_path = tmp_path / "paper-mvp-runtime.json"
    try:
        publish_test_market(context.trade_lifecycle_service, directory=tmp_path)
        state = context.account_state_manager_v2.get_state()
        identity = context.account_switch_safety_v2.identity
        result = context.trade_lifecycle_service.submit_signal(
            signal=signal(),
            order_type="MARKET",
            risk_context={
                "account_id": identity.account_id,
                "profile_name": identity.profile_name,
                "account_balance": context.portfolio_manager_v2.get_available_balance(),
                "risk_percent": context.account_switch_safety_v2._profile["risk_percent"],
                "point_value": 2.0,
                "daily_pnl": state["daily_pnl"],
                "total_drawdown": state["drawdown"],
            },
        )
        assert result["accepted"] is True
        context.runtime_lifecycle_manager.shutdown_to(file_path=state_path)
    finally:
        context.execution_state_store._durability.release()

    recovered = build_runtime_context(account_manager=manager)
    try:
        report = recovered.runtime_lifecycle_manager.start_from(file_path=state_path)
        assert report["success"] is True
        lifecycle = recovered.trade_lifecycle_service
        assert len(lifecycle.broker_connector_v2.get_fills()) == 1
        assert len(lifecycle.get_active_positions()) == 1
        assert len(lifecycle.trade_journal_v2.get_trades()) == 1
        assert len(recovered.portfolio_manager_v2.get_open_positions()) == 1
    finally:
        recovered.execution_state_store._durability.release()
