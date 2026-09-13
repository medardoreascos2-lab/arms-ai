"""Focused Phase 0 verification for the account-manager API contract."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
)
from backend.services.account_switch_safety_v2 import (
    AccountSwitchRejected,
)

from backend.tests.test_account_switch_safety_containment_v2 import (
    ADMIN_TOKEN,
    payload,
    runtime,
)


def _authorized_headers():
    return {ADMIN_TOKEN_HEADER: ADMIN_TOKEN}


def _runtime_snapshot(runtime):
    state = runtime.context.execution_state_store.capture_state()
    state.pop("captured_at", None)
    return {
        "state": state,
        "config": runtime.config.read_bytes(),
        "identity": deepcopy(runtime.safety.identity),
        "active_account": runtime.app.state.account_config_manager_v2.active_account,
        "fills": deepcopy(
            runtime.context.trade_lifecycle_service
            .broker_connector_v2
            .get_fills()
        ),
    }


def test_authorized_account_manager_reads_return_consistent_identity(runtime):
    client = runtime.client

    manager = client.get("/api/v2/dashboard/account-manager")
    assert manager.status_code == 200
    assert manager.json()["active_account"] == "A"
    assert manager.json()["firm"] == "AUDIT-A"
    assert manager.json()["account_size"] == 150000

    available = client.get(
        "/api/v2/dashboard/account-manager/available"
    )
    assert available.status_code == 200
    assert set(available.json()["accounts"]) == {"A", "B"}

    context = client.get(
        "/api/v2/dashboard/account-manager/switch-context"
    )
    assert context.status_code == 200
    assert context.json() == {
        "account_id": runtime.safety.identity.account_id,
        "profile_name": runtime.safety.identity.profile_name,
        "cross_account_switch_enabled": False,
    }

    assert context.json()["account_id"] == runtime.safety.identity.account_id
    assert context.json()["profile_name"] == runtime.safety.identity.profile_name


@pytest.mark.parametrize(
    "method,path,expected_status",
    [
        ("get", "/api/v2/dashboard/account-manager", 200),
        ("get", "/api/v2/dashboard/account-manager/available", 200),
        ("get", "/api/v2/dashboard/account-manager/switch-context", 200),
        ("post", "/api/v2/dashboard/account-manager/switch", 401),
    ],
)
def test_account_manager_authorization_scope(
    runtime,
    method,
    path,
    expected_status,
):
    client = TestClient(runtime.app)

    kwargs = {}
    if method == "post":
        kwargs["json"] = payload(runtime, "A")

    response = getattr(client, method)(path, **kwargs)

    assert response.status_code == expected_status

    if expected_status == 401:
        assert response.json()["detail"] == "admin_unauthorized"


def test_account_manager_rejects_invalid_switch_payloads_without_state_change(
    runtime,
):
    before = _runtime_snapshot(runtime)

    invalid_requests = [
        {
            "json": {"account_id": runtime.safety.identity.account_id},
        },
        {
            "json": {"profile_name": "A"},
        },
        {
            "json": {
                **payload(runtime, "A"),
                "extra": True,
            },
        },
        {
            "json": payload(runtime, "a"),
        },
        {
            "json": payload(runtime, "A", account_id="OTHER-PAPER"),
        },
        {
            "json": payload(runtime, "NOT-A-REAL-PROFILE"),
        },
    ]

    for request in invalid_requests:
        response = runtime.client.post(
            "/api/v2/dashboard/account-manager/switch",
            **request,
        )
        assert response.status_code in {409, 422}

    assert _runtime_snapshot(runtime) == before


def test_same_account_request_is_idempotent_and_preserves_identity(runtime):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        "/api/v2/dashboard/account-manager/switch",
        json=payload(runtime, "A"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ACCOUNT_UNCHANGED",
        "changed": False,
        "account_id": runtime.safety.identity.account_id,
        "profile_name": "A",
    }
    assert _runtime_snapshot(runtime) == before


def test_rejected_cross_account_request_has_no_partial_transition(runtime):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        "/api/v2/dashboard/account-manager/switch",
        json=payload(runtime, "B"),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert response.json()["changed"] is False
    assert response.json()["reason"] == (
        "account_switch_requires_coordinated_transition"
    )
    assert _runtime_snapshot(runtime) == before

    context = runtime.client.get(
        "/api/v2/dashboard/account-manager/switch-context"
    )
    assert context.status_code == 200
    assert context.json() == {
        "account_id": runtime.safety.identity.account_id,
        "profile_name": "A",
        "cross_account_switch_enabled": False,
    }


def test_switch_failure_cleans_up_safety_operation_state(runtime, monkeypatch):
    before = _runtime_snapshot(runtime)

    def fail_quiescence():
        raise AccountSwitchRejected("injected_transition_failure")

    monkeypatch.setattr(
        runtime.safety,
        "_assert_quiescent",
        fail_quiescence,
    )

    response = runtime.client.post(
        "/api/v2/dashboard/account-manager/switch",
        json=payload(runtime, "A"),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert response.json()["changed"] is False
    assert response.json()["reason"] == "injected_transition_failure"

    assert runtime.safety.durability.account_switch_in_progress is False
    assert runtime.safety.durability.active_operations == 0
    assert _runtime_snapshot(runtime) == before


def test_missing_switch_safety_authority_fails_closed_without_mutation(runtime):
    before = _runtime_snapshot(runtime)
    runtime.app.state.account_switch_safety_v2 = None

    for path, method, kwargs in [
        (
            "/api/v2/dashboard/account-manager/switch-context",
            "get",
            {},
        ),
        (
            "/api/v2/dashboard/account-manager/switch",
            "post",
            {"json": payload(runtime, "A")},
        ),
    ]:
        response = getattr(runtime.client, method)(path, **kwargs)
        assert response.status_code == 503

    assert _runtime_snapshot(runtime) == before
