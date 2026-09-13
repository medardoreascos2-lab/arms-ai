"""Phase 0 verification for both account-switch API aliases."""

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


ACCOUNT_SWITCH_PATHS = (
    "/api/v2/dashboard/account-manager/switch",
    "/api/v2/dashboard/account/switch",
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
        "active_account": (
            runtime.app.state.account_config_manager_v2.active_account
        ),
        "fills": deepcopy(
            runtime.context.trade_lifecycle_service
            .broker_connector_v2
            .get_fills()
        ),
    }


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_requires_admin_authorization(runtime, path):
    response = TestClient(runtime.app).post(
        path,
        json=payload(runtime, "A"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "admin_unauthorized"


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_accepts_validated_same_account_request(
    runtime,
    path,
):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        path,
        headers=_authorized_headers(),
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


@pytest.mark.parametrize(
    ("request_payload", "expected_status"),
    [
        ({"account_id": "PAPER-A"}, 422),
        ({"profile_name": "A"}, 422),
        ({"account_id": "PAPER-A", "profile_name": "A", "extra": True}, 422),
        ({"account_id": "OTHER-PAPER", "profile_name": "A"}, 409),
    ],
)
def test_account_switch_alias_rejects_invalid_account_or_profile_payload(
    runtime,
    request_payload,
    expected_status,
):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        "/api/v2/dashboard/account-manager/switch",
        headers=_authorized_headers(),
        json=request_payload,
    )

    assert response.status_code == expected_status
    assert _runtime_snapshot(runtime) == before


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_rejects_unknown_profile_without_mutation(
    runtime,
    path,
):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        path,
        headers=_authorized_headers(),
        json=payload(runtime, "C"),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert response.json()["changed"] is False
    assert _runtime_snapshot(runtime) == before


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_rejects_unsafe_cross_account_transition(
    runtime,
    path,
):
    before = _runtime_snapshot(runtime)

    response = runtime.client.post(
        path,
        headers=_authorized_headers(),
        json=payload(runtime, "B"),
    )

    assert response.status_code == 409
    assert response.json() == {
        "status": "ACCOUNT_SWITCH_REJECTED",
        "changed": False,
        "reason": "account_switch_requires_coordinated_transition",
        "detail": (
            "No se cambió la cuenta. El cambio requiere "
            "un runtime coherente, sin actividad pendiente "
            "y una transición coordinada."
        ),
    }
    assert _runtime_snapshot(runtime) == before


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_failure_rolls_back_operation_state(
    runtime,
    monkeypatch,
    path,
):
    before = _runtime_snapshot(runtime)

    def fail_quiescence():
        raise AccountSwitchRejected("injected_transition_failure")

    monkeypatch.setattr(
        runtime.safety,
        "_assert_quiescent",
        fail_quiescence,
    )

    response = runtime.client.post(
        path,
        headers=_authorized_headers(),
        json=payload(runtime, "A"),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert response.json()["changed"] is False
    assert response.json()["reason"] == "injected_transition_failure"

    durability = runtime.safety.durability
    assert durability.account_switch_in_progress is False
    assert durability.active_operations == 0
    assert _runtime_snapshot(runtime) == before


@pytest.mark.parametrize("path", ACCOUNT_SWITCH_PATHS)
def test_account_switch_alias_fails_closed_on_runtime_identity_error(
    runtime,
    monkeypatch,
    path,
):
    before = _runtime_snapshot(runtime)

    def fail_identity():
        raise ValueError("identity_validation_failed")

    monkeypatch.setattr(
        runtime.safety,
        "_assert_identity",
        fail_identity,
    )

    response = runtime.client.post(
        path,
        headers=_authorized_headers(),
        json=payload(runtime, "A"),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "ACCOUNT_SWITCH_REJECTED"
    assert response.json()["changed"] is False
    assert response.json()["reason"] == "runtime_safety_unproven"

    durability = runtime.safety.durability
    assert durability.account_switch_in_progress is False
    assert durability.active_operations == 0
    assert _runtime_snapshot(runtime) == before


def test_account_switch_runtime_identity_remains_consistent_after_both_aliases(
    runtime,
):
    before = _runtime_snapshot(runtime)

    for path in ACCOUNT_SWITCH_PATHS:
        response = runtime.client.post(
            path,
            headers=_authorized_headers(),
            json=payload(runtime, "A"),
        )

        assert response.status_code == 200
        assert response.json()["account_id"] == runtime.safety.identity.account_id
        assert response.json()["profile_name"] == "A"

    manager = runtime.client.get(
        "/api/v2/dashboard/account-manager",
        headers=_authorized_headers(),
    )
    assert manager.status_code == 200
    assert manager.json()["active_account"] == "A"

    context = runtime.client.get(
        "/api/v2/dashboard/account-manager/switch-context",
        headers=_authorized_headers(),
    )
    assert context.status_code == 200
    assert context.json() == {
        "account_id": runtime.safety.identity.account_id,
        "profile_name": "A",
        "cross_account_switch_enabled": False,
    }

    assert _runtime_snapshot(runtime) == before


def test_account_switch_aliases_have_consistent_rejection_contract(runtime):
    responses = []

    for path in ACCOUNT_SWITCH_PATHS:
        response = runtime.client.post(
            path,
            headers=_authorized_headers(),
            json=payload(runtime, "B"),
        )
        responses.append(response)

    assert [response.status_code for response in responses] == [409, 409]
    assert [response.json() for response in responses] == [
        responses[0].json(),
        responses[0].json(),
    ]
