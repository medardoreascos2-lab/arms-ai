from datetime import datetime, timedelta, timezone

import pytest

from backend.market_data.sim_operator_binding_v2 import (
    OperatorSimBindingV2,
    OperatorSimBindingLatchV2,
    assess_operator_sim_binding,
    derive_private_ref,
)


SECRET = b"synthetic-installation-secret-for-tests"
NOW = datetime(2026, 9, 26, tzinfo=timezone.utc)


def binding():
    return OperatorSimBindingV2(
        installation_ref=derive_private_ref(
            SECRET,
            domain="installation",
            value="synthetic-installation-A",
        ),
        account_ref=derive_private_ref(
            SECRET,
            domain="account",
            value="synthetic-account-A",
        ),
        connection_ref=derive_private_ref(
            SECRET,
            domain="connection",
            value="synthetic-connection-A",
        ),
        label_ref=derive_private_ref(
            SECRET,
            domain="label",
            value="Sim101",
        ),
        provider="Simulator",
        connection_mode="Live",
        enabled=True,
        operator_approved=True,
    )


def snapshot():
    value = binding()
    return {
        "installation_ref": value.installation_ref,
        "account_ref": value.account_ref,
        "connection_ref": value.connection_ref,
        "label_ref": value.label_ref,
        "provider": "Simulator",
        "connection_mode": "Live",
        "account_count": 1,
        "connected": True,
        "revoked": False,
        "observed_at": NOW.isoformat(),
        "runtime_ref": "runtime-A",
        "connection_epoch": "epoch-A",
    }


def test_private_refs_are_keyed_and_domain_separated():
    account = derive_private_ref(
        SECRET,
        domain="account",
        value="same-value",
    )
    connection = derive_private_ref(
        SECRET,
        domain="connection",
        value="same-value",
    )

    assert len(account) == 64
    assert len(connection) == 64
    assert account != connection

    other_secret = derive_private_ref(
        b"different-secret",
        domain="account",
        value="same-value",
    )

    assert account != other_secret


def test_valid_operator_bound_native_sim_can_be_future_eligible_without_order_authority():
    result = assess_operator_sim_binding(
        snapshot(),
        binding(),
        NOW,
    )

    assert result["sim_discovery_status"] == "OPERATOR_BOUND_NATIVE"
    assert result["sim_classification_status"] == "PROVEN_SIMULATION"
    assert result["sim_binding_status"] == "BOUND"
    assert result["future_sim_eligible"] is True

    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False

    assert not any(
        key.endswith("_ref")
        for key in result
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"provider": "Provider31"},
        {"connection_mode": "Simulation"},
        {"account_count": 2},
        {"connected": False},
        {"revoked": True},
        {"account_ref": "0" * 64},
        {"connection_ref": "0" * 64},
        {"installation_ref": "0" * 64},
        {"label_ref": "0" * 64},
    ],
)
def test_any_identity_or_simulation_mismatch_fails_closed(mutation):
    candidate = {
        **snapshot(),
        **mutation,
    }

    result = assess_operator_sim_binding(
        candidate,
        binding(),
        NOW,
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False


def test_stale_or_future_observation_fails_closed():
    for observed in (
        NOW - timedelta(seconds=16),
        NOW + timedelta(seconds=1),
    ):
        candidate = {
            **snapshot(),
            "observed_at": observed.isoformat(),
        }

        result = assess_operator_sim_binding(
            candidate,
            binding(),
            NOW,
        )

        assert result["future_sim_eligible"] is False
        assert result["sim_execution_authority"] == "DISABLED"


def test_operator_approval_and_enabled_binding_are_both_required():
    base = binding()

    for value in (
        OperatorSimBindingV2(
            **{
                **base.__dict__,
                "enabled": False,
            }
        ),
        OperatorSimBindingV2(
            **{
                **base.__dict__,
                "operator_approved": False,
            }
        ),
    ):
        result = assess_operator_sim_binding(
            snapshot(),
            value,
            NOW,
        )

        assert result["future_sim_eligible"] is False
        assert result["sim_execution_authority"] == "DISABLED"


def test_runtime_latch_revokes_permanently_on_identity_change():
    value = binding()
    first = snapshot()

    latch = OperatorSimBindingLatchV2(
        value,
        runtime_ref="runtime-A",
        connection_epoch="epoch-A",
    )

    first["discovery_sequence"] = 0

    result = latch.observe(
        first,
        NOW,
    )

    assert result["future_sim_eligible"] is True
    assert result["sim_runtime_revalidation"] == "PASS"

    changed = {
        **snapshot(),
        "discovery_sequence": 1,
        "connection_ref": "0" * 64,
        "observed_at": (
            NOW + timedelta(seconds=1)
        ).isoformat(),
    }

    result = latch.observe(
        changed,
        NOW + timedelta(seconds=1),
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_runtime_revalidation"] == "REVOKED"

    restored = {
        **snapshot(),
        "discovery_sequence": 1,
        "observed_at": (
            NOW + timedelta(seconds=1)
        ).isoformat(),
    }

    result = latch.observe(
        restored,
        NOW + timedelta(seconds=1),
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_runtime_revalidation"] == "REVOKED"
    assert result["sim_execution_authority"] == "DISABLED"


class ForbiddenHandle:
    def __getattribute__(self, name):
        raise AssertionError("handle must not be inspected")


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        "not-a-dict",
        False,
    ],
)
def test_malformed_snapshot_never_grants_eligibility(bad):
    result = assess_operator_sim_binding(
        bad,
        binding(),
        NOW,
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False


def test_handle_snapshot_is_rejected_without_attribute_access():
    result = assess_operator_sim_binding(
        ForbiddenHandle(),
        binding(),
        NOW,
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_execution_authority"] == "DISABLED"
    assert result["external_order_authority"] is False


@pytest.mark.parametrize(
    "field",
    [
        "installation_ref",
        "account_ref",
        "connection_ref",
        "label_ref",
    ],
)
def test_malformed_binding_ref_fails_closed(field):
    base = binding()

    value = OperatorSimBindingV2(
        **{
            **base.__dict__,
            field: "not-a-valid-ref",
        }
    )

    result = assess_operator_sim_binding(
        snapshot(),
        value,
        NOW,
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_execution_authority"] == "DISABLED"


@pytest.mark.parametrize(
    "case",
    [
        "duplicate",
        "gap",
        "out_of_order",
        "runtime_changed",
        "epoch_changed",
        "clock_regression",
    ],
)
def test_runtime_sequence_or_epoch_change_revokes(case):
    value = binding()

    latch = OperatorSimBindingLatchV2(
        value,
        runtime_ref="runtime-A",
        connection_epoch="epoch-A",
    )

    first = {
        **snapshot(),
        "discovery_sequence": 0,
    }

    assert latch.observe(
        first,
        NOW,
    )["future_sim_eligible"] is True

    second = {
        **snapshot(),
        "discovery_sequence": 1,
        "observed_at": (
            NOW + timedelta(seconds=1)
        ).isoformat(),
    }

    if case == "duplicate":
        second["discovery_sequence"] = 0
    elif case == "gap":
        second["discovery_sequence"] = 2
    elif case == "out_of_order":
        second["discovery_sequence"] = -1
    elif case == "runtime_changed":
        second["runtime_ref"] = "runtime-B"
    elif case == "epoch_changed":
        second["connection_epoch"] = "epoch-B"
    elif case == "clock_regression":
        second["observed_at"] = (
            NOW - timedelta(seconds=1)
        ).isoformat()

    result = latch.observe(
        second,
        NOW + timedelta(seconds=1),
    )

    assert result["future_sim_eligible"] is False
    assert result["sim_runtime_revalidation"] == "REVOKED"
    assert result["sim_execution_authority"] == "DISABLED"


def test_module_has_no_io_environment_or_order_authority_surface():
    import ast
    from pathlib import Path

    path = Path(
        "backend/market_data/sim_operator_binding_v2.py"
    )

    tree = ast.parse(
        path.read_text(encoding="utf-8")
    )

    forbidden_imports = {
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "requests",
    }

    forbidden_calls = {
        "open",
        "Submit",
        "submit_order",
        "CreateOrder",
        "Cancel",
        "Flatten",
        "ResetSimulationAccount",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(
                alias.name not in forbidden_imports
                for alias in node.names
            )

        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_imports

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
            else:
                name = getattr(
                    node.func,
                    "attr",
                    None,
                )

            assert name not in forbidden_calls
