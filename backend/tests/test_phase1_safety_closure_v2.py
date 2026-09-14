"""Executable Phase 1 safety-closure characterization.

These tests verify the existing safety boundaries without enabling LIVE trading
or introducing a new execution path.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)
from backend.services.durable_execution_state_v2 import (
    AccountAdmissionRejected,
    DurableExecutionStateV2,
    seal,
    verify,
)
from backend.connectors.paper_broker_connector_v2 import (
    PaperBrokerConnectorV2,
)

from backend.tests.test_trade_lifecycle_service_v2 import (
    build_service,
    build_valid_signal,
)


def _execution_state(service):
    broker = service.broker_connector_v2
    return {
        "orders": broker.get_orders(),
        "fills": broker.get_fills(),
        "broker_positions": broker.get_positions(),
        "active_positions": service.get_active_positions(),
    }


def test_rejected_trade_submission_has_zero_execution_side_effects():
    service = build_service()
    signal = build_valid_signal()
    signal.update(
        {
            "approved": False,
            "status": "BLOCKED",
            "decision": "DO_NOT_SEND",
            "blocking_reasons": ["unsafe_signal"],
        }
    )

    before = _execution_state(service)

    result = service.submit_signal(
        signal=signal,
        order_type="MARKET",
    )

    assert result["accepted"] is False
    assert result["reason"] == "signal_not_approved"
    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None
    assert result["active_position_id"] is None
    assert _execution_state(service) == before


def test_invalid_authorization_fails_closed():
    authority = AdminAuthorizationV2(token="expected-admin-token")

    assert authority.is_authorized(None) is False
    assert authority.is_authorized("") is False
    assert authority.is_authorized("wrong-token") is False

    with pytest.raises(PermissionError, match="admin_unauthorized"):
        authority.require_authorized("wrong-token")


def test_account_transition_barrier_rejects_new_operations():
    durability = DurableExecutionStateV2(
        store=SimpleNamespace(),
    )
    durability.account_switch_in_progress = True

    with pytest.raises(
        AccountAdmissionRejected,
        match="account_switch_in_progress",
    ):
        with durability.admission_barrier():
            pass


def test_risk_rejection_has_zero_execution_side_effects():
    service = build_service()
    before = _execution_state(service)

    result = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": -3001.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
    )

    assert result["accepted"] is False
    assert result["reason"] == "risk_blocked"
    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None
    assert _execution_state(service) == before


def test_recovery_ambiguity_is_rejected_before_runtime_authorization():
    state = {
        "execution_records": [],
        "account_state": {
            "account_id": "PAPER-ACCOUNT",
        },
    }
    pending_state = seal(
        state,
        generation=1,
        phase="PENDING",
    )

    with pytest.raises(
        ValueError,
        match="Incomplete or unsupported durable operation",
    ):
        verify(pending_state)


def test_successful_execution_is_explicitly_paper_only():
    service = build_service()

    assert isinstance(
        service.paper_execution_engine,
        PaperExecutionEngineV2,
    )
    assert isinstance(
        service.broker_connector_v2,
        PaperBrokerConnectorV2,
    )
    assert service.execution_manager.execution_mode == "PAPER"
    assert service.broker_connector_v2.execution_mode == "PAPER"

    result = service.submit_signal(
        signal=build_valid_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 17000.0,
            "risk_percent": 0.5,
            "point_value": 2.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
    )

    assert result["accepted"] is True
    assert result["execution"]["status"] == "FILLED"
    assert result["execution"]["execution_mode"] == "PAPER"
    assert result["execution"]["broker"] == "ARMS_PAPER"
    assert result["execution"]["broker"] != "LIVE"
