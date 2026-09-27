import pytest

from backend.services.sim_execution_activation_gate_v2 import (
    SimExecutionActivationGateV2,
)


def good_binding():
    return {
        "future_sim_eligible": True,
        "sim_runtime_revalidation": "PASS",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


def good_health():
    return {
        "healthy": True,
        "connected": True,
        "execution_mode": "SIM",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }


def good_recovery():
    return {
        "status": "CONFIRMED_NOT_EXECUTED",
        "resolved": True,
        "executed": False,
    }


def good_native_inventory():
    return {
        "ambiguous_orders": 0,
        "ambiguous_positions": 0,
        "unresolved_orders": 0,
        "unresolved_positions": 0,
    }


def good_ack_capability():
    return {
        "ack_submit_enabled": True,
        "scope": "SIM_ACK_TEST_ONLY",
    }


def good_mutation_capability():
    return {
        "native_mutation_enabled": True,
        "scope": "SIM_MUTATION_TEST_ONLY",
    }


def gate():
    return SimExecutionActivationGateV2(
        binding_probe=good_binding,
        health_probe=good_health,
        recovery_probe=good_recovery,
        native_inventory_probe=good_native_inventory,
        ack_capability_probe=good_ack_capability,
        mutation_capability_probe=good_mutation_capability,
    )


def test_gate_starts_disarmed():
    value = gate()

    status = value.status()

    assert status["state"] == "DISABLED"
    assert status["armed"] is False
    assert status["sim_execution_authority"] == "DISABLED"
    assert status["external_order_authority"] is False


def test_arm_requires_explicit_operator_token():
    value = gate()

    for bad in (
        None,
        "",
        "   ",
        "wrong",
    ):
        with pytest.raises(
            ValueError,
            match="explicit operator arm token required",
        ):
            value.arm(
                operator_token=bad,
            )


def test_all_green_conditions_allow_armed_state():
    value = gate()

    result = value.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    assert result["state"] == "ARMED"
    assert result["armed"] is True

    # Public binding projection still remains disabled.
    assert result["sim_execution_authority"] == "ARMED"
    assert result["external_order_authority"] is True


@pytest.mark.parametrize(
    ("name", "replacement", "reason"),
    [
        (
            "binding",
            lambda: {
                "future_sim_eligible": False,
                "sim_runtime_revalidation": "REVOKED",
                "sim_execution_authority": "DISABLED",
                "external_order_authority": False,
            },
            "binding_not_eligible",
        ),
        (
            "health",
            lambda: {
                "healthy": False,
                "connected": False,
                "execution_mode": "SIM",
                "sim_execution_authority": "DISABLED",
                "external_order_authority": False,
            },
            "native_health_not_ready",
        ),
        (
            "recovery",
            lambda: {
                "status": "RECOVERY_REQUIRED",
                "resolved": False,
                "executed": False,
            },
            "pending_recovery_unresolved",
        ),
        (
            "inventory",
            lambda: {
                "ambiguous_orders": 1,
                "ambiguous_positions": 0,
                "unresolved_orders": 0,
                "unresolved_positions": 0,
            },
            "native_inventory_ambiguous",
        ),
        (
            "ack",
            lambda: {
                "ack_submit_enabled": False,
                "scope": "SIM_ACK_TEST_ONLY",
            },
            "ack_capability_missing",
        ),
        (
            "mutation",
            lambda: {
                "native_mutation_enabled": False,
                "scope": "SIM_MUTATION_TEST_ONLY",
            },
            "mutation_capability_missing",
        ),
    ],
)
def test_any_failed_precondition_blocks_arm(
    name,
    replacement,
    reason,
):
    kwargs = dict(
        binding_probe=good_binding,
        health_probe=good_health,
        recovery_probe=good_recovery,
        native_inventory_probe=good_native_inventory,
        ack_capability_probe=good_ack_capability,
        mutation_capability_probe=good_mutation_capability,
    )

    mapping = {
        "binding": "binding_probe",
        "health": "health_probe",
        "recovery": "recovery_probe",
        "inventory": "native_inventory_probe",
        "ack": "ack_capability_probe",
        "mutation": "mutation_capability_probe",
    }

    kwargs[
        mapping[name]
    ] = replacement

    value = SimExecutionActivationGateV2(
        **kwargs
    )

    result = value.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )

    assert result["state"] == "DISABLED"
    assert result["armed"] is False
    assert result["reason"] == reason
    assert result["external_order_authority"] is False


def test_armed_gate_revalidates_and_revokes_on_binding_loss():
    state = {
        "binding": good_binding(),
    }

    value = SimExecutionActivationGateV2(
        binding_probe=lambda: dict(
            state["binding"]
        ),
        health_probe=good_health,
        recovery_probe=good_recovery,
        native_inventory_probe=good_native_inventory,
        ack_capability_probe=good_ack_capability,
        mutation_capability_probe=good_mutation_capability,
    )

    assert value.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )["armed"] is True

    state["binding"] = {
        "future_sim_eligible": False,
        "sim_runtime_revalidation": "REVOKED",
        "sim_execution_authority": "DISABLED",
        "external_order_authority": False,
    }

    result = value.revalidate()

    assert result["state"] == "REVOKED"
    assert result["armed"] is False
    assert result["reason"] == "binding_not_eligible"
    assert result["external_order_authority"] is False


def test_revoke_is_terminal_for_current_gate_instance():
    value = gate()

    assert value.arm(
        operator_token="ARM_SIM_EXECUTION_V2",
    )["armed"] is True

    value.revoke(
        reason="operator_revoke",
    )

    result = value.status()

    assert result["state"] == "REVOKED"
    assert result["armed"] is False
    assert result["reason"] == "operator_revoke"

    with pytest.raises(
        RuntimeError,
        match="activation gate is revoked",
    ):
        value.arm(
            operator_token="ARM_SIM_EXECUTION_V2",
        )


def test_gate_has_no_native_order_transport_surface():
    value = gate()

    forbidden = (
        "submit_order",
        "modify_order",
        "cancel_order",
        "close_position",
        "close_partial",
    )

    for name in forbidden:
        assert not hasattr(
            value,
            name,
        )
