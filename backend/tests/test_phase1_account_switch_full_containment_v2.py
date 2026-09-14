"""Phase 1 account-switch containment and fail-closed characterization tests.

These tests extend the existing account-switch coverage without changing
production code. They verify that account transitions do not leak active
execution, risk, portfolio, lifecycle, durable-state, identity, or
authorization state across runtimes.
"""

from copy import deepcopy

import pytest

from backend.api.admin_authorization_dependency_v2 import ADMIN_TOKEN_HEADER
from backend.services.durable_execution_state_v2 import (
    AccountAdmissionRejected,
)
from backend.services.account_switch_safety_v2 import (
    AccountSwitchRejected,
)

from backend.tests.test_account_runtime_transition_v2 import (
    ADMIN_TOKEN,
    hosted,
    signal,
    target,
    trade,
)


URLS = (
    "/api/v2/dashboard/account-manager/switch",
    "/api/v2/dashboard/account/switch",
)


def _headers():
    return {ADMIN_TOKEN_HEADER: ADMIN_TOKEN}


def _snapshot(host):
    value = host.c.published.runtime.execution_state_store.capture_state()
    value.pop("captured_at", None)
    value.pop("account_identity", None)
    return value


def _switch(host, profile_name, url=URLS[0]):
    return host.client.post(
        url,
        json=target(host, profile_name),
        headers=_headers(),
    )


def _assert_rejected_switch(host, response, reason):
    assert response.status_code == 409, response.text
    body = response.json()
    assert body["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert body["changed"] is False
    assert body["reason"] == reason


@pytest.mark.parametrize("url", URLS)
def test_pending_execution_blocks_switch_without_selector_or_state_leak(
    hosted,
    url,
):
    host = hosted
    runtime = host.c.published.runtime
    durability = runtime.execution_state_store._durability

    before_state = _snapshot(host)
    before_config = host.config.read_bytes()
    before_identity = deepcopy(host.c.identity)
    before_generation = host.c.published.generation

    durability.operation = {
        "operation_id": "phase1-pending-operation",
        "generation": before_generation + 1,
    }

    try:
        response = _switch(host, "B", url)
    finally:
        durability.operation = None

    _assert_rejected_switch(host, response, "durable_operation_pending")
    assert host.config.read_bytes() == before_config
    assert _snapshot(host) == before_state
    assert host.c.identity == before_identity
    assert host.c.published.generation == before_generation
    assert host.c.published.runtime is runtime
    assert runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_active_lifecycle_state_blocks_switch_and_preserves_account_runtime(
    hosted,
):
    host = hosted
    opened = trade(host)
    assert opened["accepted"] is True

    runtime = host.c.published.runtime
    before_state = _snapshot(host)
    before_config = host.config.read_bytes()
    before_identity = deepcopy(host.c.identity)
    source_path = runtime.execution_state_store._durability.path

    response = _switch(host, "B")

    _assert_rejected_switch(host, response, "lifecycle_position_active")
    assert host.config.read_bytes() == before_config
    assert _snapshot(host) == before_state
    assert host.c.identity == before_identity
    assert host.c.published.runtime is runtime
    assert runtime.execution_state_store._durability.path == source_path
    assert len(runtime.trade_lifecycle_service.get_active_positions()) == 1
    assert len(runtime.portfolio_manager_v2.get_open_positions()) == 1


def test_portfolio_state_does_not_leak_to_target_and_is_restored_to_source(
    hosted,
):
    host = hosted

    source_trade = trade(host, close_price=10010.0)
    assert source_trade["accepted"] is True

    source = host.c.published.runtime
    source_history = deepcopy(source.trade_history_manager.get_history())
    source_journal = deepcopy(
        source.trade_lifecycle_service.trade_journal_v2.get_trades()
    )
    assert source_history
    assert source_journal

    response = _switch(host, "B")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ACCOUNT_CHANGED"

    target_runtime = host.c.published.runtime
    assert target_runtime is not source
    assert target_runtime.portfolio_manager_v2.get_open_positions() == []
    assert target_runtime.trade_history_manager.get_history() == []
    assert target_runtime.trade_lifecycle_service.trade_journal_v2.get_trades() == []
    assert target_runtime.account_state_manager_v2.get_state()["daily_pnl"] == 0.0
    assert target_runtime.account_state_manager_v2.get_state()["starting_balance"] == 50000

    response = _switch(host, "A")
    assert response.status_code == 200, response.text
    restored = host.c.published.runtime

    assert restored.portfolio_manager_v2.get_open_positions() == []
    assert restored.trade_history_manager.get_history() == source_history
    assert (
        restored.trade_lifecycle_service.trade_journal_v2.get_trades()
        == source_journal
    )


def test_risk_state_isolated_between_accounts_and_restored_on_switch_back(
    hosted,
):
    host = hosted
    source = host.c.published.runtime
    source.account_state_manager_v2.record_daily_pnl(daily_pnl=-3000.0)

    source_state = source.account_state_manager_v2.get_state()
    assert source_state["trading_blocked"] is True
    assert source_state["daily_pnl"] == -3000.0

    response = _switch(host, "B")
    assert response.status_code == 200, response.text

    target_runtime = host.c.published.runtime
    target_state = target_runtime.account_state_manager_v2.get_state()

    assert target_state["trading_blocked"] is False
    assert target_state["daily_pnl"] == 0.0
    assert target_state["starting_balance"] == 50000
    assert target_runtime.risk_manager_v2.maximum_daily_loss == 1000
    assert target_runtime.risk_manager_v2.maximum_total_drawdown == 2000

    response = _switch(host, "A")
    assert response.status_code == 200, response.text

    restored_state = host.c.published.runtime.account_state_manager_v2.get_state()
    assert restored_state["trading_blocked"] is True
    assert restored_state["daily_pnl"] == -3000.0


def test_durable_state_namespace_identity_and_generation_do_not_leak(
    hosted,
):
    host = hosted
    source_bundle = host.c.published
    source_runtime = source_bundle.runtime
    source_store = source_runtime.execution_state_store
    source_path = source_store._durability.path
    source_identity = deepcopy(source_store.account_identity)
    source_generation = source_bundle.generation

    response = _switch(host, "B")
    assert response.status_code == 200, response.text

    target_bundle = host.c.published
    target_runtime = target_bundle.runtime
    target_store = target_runtime.execution_state_store

    assert target_bundle.generation == source_generation + 1
    assert target_store.account_identity["account_id"] != source_identity["account_id"]
    assert target_store.account_identity["profile_name"] == "B"
    assert target_store.account_identity["runtime_generation"] == target_bundle.generation
    assert target_store._durability.path.parent != source_path.parent
    assert target_store._durability.path.parent.name == target_store.account_identity["account_id"]
    assert source_store._durability.retired is True

    source_snapshot = source_path.read_bytes()
    assert source_snapshot

    source_state = source_store.capture_state()
    assert source_state["account_identity"] == source_identity


@pytest.mark.parametrize("url", URLS)
def test_unauthorized_switch_cannot_change_authorization_or_account_state(
    hosted,
    url,
):
    host = hosted
    before_config = host.config.read_bytes()
    before_identity = deepcopy(host.c.identity)
    before_generation = host.c.published.generation
    before_state = _snapshot(host)

    response = host.client.request(
        "POST",
        url,
        json=target(host, "B"),
        headers={
            "X-ARMS-ADMIN-TOKEN": "invalid-admin-token",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "admin_unauthorized"
    assert host.config.read_bytes() == before_config
    assert host.c.identity == before_identity
    assert host.c.published.generation == before_generation
    assert _snapshot(host) == before_state
    assert host.c.published.runtime.trade_lifecycle_service.broker_connector_v2.get_fills() == []


def test_precommit_switch_failure_rolls_back_and_keeps_source_executable(
    hosted,
    monkeypatch,
):
    host = hosted
    source = host.c.published.runtime
    before_state = _snapshot(host)
    before_config = host.config.read_bytes()
    before_identity = deepcopy(host.c.identity)

    def fail_at_build_target(phase):
        if phase == "BUILD_TARGET":
            raise ValueError("injected precommit failure")

    monkeypatch.setattr(host.c, "_step", fail_at_build_target)

    response = _switch(host, "B")

    _assert_rejected_switch(host, response, "account_transition_failed")
    assert host.c.failed is False
    assert host.c.switching is False
    assert host.c.phase == "READY"
    assert host.c.published.runtime is source
    assert host.c.identity == before_identity
    assert host.config.read_bytes() == before_config
    assert _snapshot(host) == before_state

    result = trade(host, close_price=10010.0)
    assert result["accepted"] is True
    assert result["execution_risk_gate"]["account"] == "A"


def test_postcommit_failure_enters_fail_closed_state_and_prevents_execution(
    hosted,
    monkeypatch,
):
    host = hosted

    def fail_after_publication(phase):
        if phase == "AFTER_PUBLISH":
            raise ValueError("injected postcommit failure")

    monkeypatch.setattr(host.c, "_step", fail_after_publication)

    response = _switch(host, "B")

    assert response.status_code == 503, response.text
    body = response.json()
    assert body["status"] == "ACCOUNT_TRANSITION_UNCERTAIN"
    assert body["changed"] is None
    assert host.c.failed is True
    assert host.c.phase == "FAILED"

    committed = host.c._published
    assert committed is not None
    assert committed.runtime.account_switch_safety_v2.identity.profile_name == "B"
    assert (
        committed.runtime.account_switch_safety_v2.identity.account_id
        == host.c._catalog["active_account_id"]
    )
    assert committed.runtime.execution_state_store._durability.retired is True

    with pytest.raises(
        AccountSwitchRejected,
        match="account_runtime_unavailable",
    ):
        _ = host.c.published

    with pytest.raises(
        AccountSwitchRejected,
        match="account_runtime_unavailable",
    ):
        _ = host.c.identity

    blocked = host.client.post(
        "/v2/trades/submit",
        json={
            "signal": signal(),
            "order_type": "MARKET",
        },
        headers=_headers(),
    )

    assert blocked.status_code == 409
    assert (
        committed.runtime.trade_lifecycle_service
        .broker_connector_v2.get_fills()
        == []
    )

    with pytest.raises(AccountAdmissionRejected):
        committed.runtime.execution_manager.prepare_order(
            signal=signal(),
            order_type="MARKET",
        )


def test_retired_source_runtime_cannot_submit_after_successful_switch(hosted):
    host = hosted
    source = host.c.published.runtime

    response = _switch(host, "B")
    assert response.status_code == 200, response.text

    assert source.execution_state_store._durability.retired is True

    denied = source.trade_lifecycle_service.submit_signal(
        signal=signal(),
        order_type="MARKET",
    )
    assert denied["accepted"] is False
    assert denied["prepared_order"] is None
    assert denied["execution"] is None

    with pytest.raises(AccountAdmissionRejected):
        source.execution_manager.prepare_order(
            signal=signal(),
            order_type="MARKET",
        )

    with pytest.raises(AccountAdmissionRejected):
        source.paper_execution_engine.execute(prepared_order={})

    with pytest.raises(AccountAdmissionRejected):
        source.trade_lifecycle_service.broker_connector_v2.submit_order(
            prepared_order={},
        )

    assert host.c.published.runtime is not source
    assert host.c.published.runtime.account_switch_safety_v2.identity.profile_name == "B"
