import pytest


MODULE = (
    "backend.services."
    "sim_first_native_entry_preflight_v2"
)


def load_preflight():
    module = __import__(
        MODULE,
        fromlist=[
            "SimFirstNativeEntryPreflightV2"
        ],
    )

    return (
        module
        .SimFirstNativeEntryPreflightV2
    )


def base_input():
    return {
        "account_name": "Sim101",
        "provider": "Simulator",
        "connection_status": "Connected",
        "physical_test_readiness": (
            "PHYSICAL_TEST_READY"
        ),
        "position_state": "FLAT",
        "active_order_count": 0,
        "activation_valid": True,
        "activation_consumed": False,
        "command_id": "cmd-entry-1",
        "operation_id": "op-entry-1",
        "client_order_id": "op-entry-1",
        "native_submit_enabled": False,
        "auto_retry_allowed": False,
        "recovery_available": True,
        "native_evidence_available": True,
    }


def evaluate(**overrides):
    Preflight = load_preflight()

    payload = base_input()
    payload.update(overrides)

    value = Preflight()

    return value.evaluate(**payload)


def test_all_conditions_ready_but_submit_still_disabled():
    result = evaluate()

    assert result["status"] == "READY_FOR_OPERATOR_REVIEW"
    assert result["eligible"] is True

    assert (
        result["native_submit_enabled"]
        is False
    )

    assert (
        result["automatic_retry_allowed"]
        is False
    )

    assert result["blocking_reasons"] == []


def test_wrong_account_fails_closed():
    result = evaluate(
        account_name="Sim102"
    )

    assert result["status"] == "BLOCKED"
    assert result["eligible"] is False
    assert "ACCOUNT_NOT_SIM101" in (
        result["blocking_reasons"]
    )


def test_wrong_provider_fails_closed():
    result = evaluate(
        provider="Continuum"
    )

    assert result["status"] == "BLOCKED"
    assert "PROVIDER_NOT_SIMULATOR" in (
        result["blocking_reasons"]
    )


def test_disconnected_fails_closed():
    result = evaluate(
        connection_status="Disconnected"
    )

    assert result["status"] == "BLOCKED"
    assert "CONNECTION_NOT_CONNECTED" in (
        result["blocking_reasons"]
    )


def test_market_session_closed_fails_closed():
    result = evaluate(
        physical_test_readiness=(
            "MARKET_SESSION_CLOSED"
        )
    )

    assert result["status"] == "BLOCKED"
    assert "PHYSICAL_TEST_NOT_READY" in (
        result["blocking_reasons"]
    )


@pytest.mark.parametrize(
    "state",
    [
        "LONG",
        "SHORT",
        "UNKNOWN",
    ],
)
def test_non_flat_position_fails_closed(
    state,
):
    result = evaluate(
        position_state=state
    )

    assert result["status"] == "BLOCKED"
    assert "POSITION_NOT_FLAT" in (
        result["blocking_reasons"]
    )


def test_active_native_order_fails_closed():
    result = evaluate(
        active_order_count=1
    )

    assert result["status"] == "BLOCKED"
    assert "ACTIVE_NATIVE_ORDERS_PRESENT" in (
        result["blocking_reasons"]
    )


def test_invalid_activation_fails_closed():
    result = evaluate(
        activation_valid=False
    )

    assert result["status"] == "BLOCKED"
    assert "ACTIVATION_INVALID" in (
        result["blocking_reasons"]
    )


def test_consumed_activation_fails_closed():
    result = evaluate(
        activation_consumed=True
    )

    assert result["status"] == "BLOCKED"
    assert "ACTIVATION_ALREADY_CONSUMED" in (
        result["blocking_reasons"]
    )


def test_operation_identity_mismatch_fails_closed():
    result = evaluate(
        client_order_id="op-other"
    )

    assert result["status"] == "BLOCKED"
    assert "DURABLE_IDENTITY_MISMATCH" in (
        result["blocking_reasons"]
    )


def test_missing_command_id_fails_closed():
    result = evaluate(
        command_id=""
    )

    assert result["status"] == "BLOCKED"
    assert "COMMAND_ID_INVALID" in (
        result["blocking_reasons"]
    )


def test_native_submit_must_remain_disabled():
    result = evaluate(
        native_submit_enabled=True
    )

    assert result["status"] == "BLOCKED"
    assert "NATIVE_SUBMIT_ALREADY_ENABLED" in (
        result["blocking_reasons"]
    )


def test_auto_retry_must_remain_false():
    result = evaluate(
        auto_retry_allowed=True
    )

    assert result["status"] == "BLOCKED"
    assert "AUTO_RETRY_NOT_FORBIDDEN" in (
        result["blocking_reasons"]
    )


def test_recovery_must_be_available():
    result = evaluate(
        recovery_available=False
    )

    assert result["status"] == "BLOCKED"
    assert "RECOVERY_UNAVAILABLE" in (
        result["blocking_reasons"]
    )


def test_native_evidence_must_be_available():
    result = evaluate(
        native_evidence_available=False
    )

    assert result["status"] == "BLOCKED"
    assert "NATIVE_EVIDENCE_UNAVAILABLE" in (
        result["blocking_reasons"]
    )


def test_multiple_failures_are_all_reported():
    result = evaluate(
        provider="OTHER",
        connection_status="Disconnected",
        position_state="LONG",
        active_order_count=3,
    )

    assert result["eligible"] is False

    assert set(
        result["blocking_reasons"]
    ) >= {
        "PROVIDER_NOT_SIMULATOR",
        "CONNECTION_NOT_CONNECTED",
        "POSITION_NOT_FLAT",
        "ACTIVE_NATIVE_ORDERS_PRESENT",
    }


def test_preflight_has_no_execution_surface():
    Preflight = load_preflight()

    value = Preflight()

    for forbidden in (
        "submit_order",
        "cancel_order",
        "modify_order",
        "close_position",
        "close_partial",
        "flatten",
        "execute",
    ):
        assert not hasattr(
            value,
            forbidden,
        )
