"""Approved commissioning inputs, isolated DPAPI and disabled runtime only."""
from copy import deepcopy
from dataclasses import asdict
import json
import os
from pathlib import Path
import re

import pytest

from backend.accounts.account_registry_v1 import AccountRegistryV1
from backend.config.api_settings import APISettings
from backend.services import sim_native_commissioning_policy_v1 as policy
from backend.services.sim_native_runtime_v3 import build_native_sim_runtime
from backend.tests.test_controlled_sim_operation_v3 import BINDING, KEY
from backend.tests.test_sim_native_config_publisher_v3 import isolated
from tools import publish_sim_native_config_v3 as operator


def document():
    return json.loads(policy.POLICY_PATH.read_text())


def runtime(selected, root):
    return build_native_sim_runtime(binding=BINDING, namespace_root=root, authority_key=KEY,
        runtime_evidence=operator._no_runtime_evidence, api_settings=selected.api_settings,
        protection_timeout_us=selected.protection_timeout_us, recovery_timeout_us=selected.recovery_timeout_us)


def test_exact_approved_values_and_no_environment_dependency(monkeypatch):
    approved = dict(zip(policy.FLOAT_FIELDS + policy.INT_FIELDS, (30., 2., 1., 100., 5., 1., .8, .8, 30, 1)))
    for name in approved:
        monkeypatch.setenv("ARMS_" + name.upper(), "unusable-global-value")
    before = dict(os.environ)
    result = policy.load()
    assert {k: getattr(result.api_settings, k) for k in approved} == approved
    assert result.protection_timeout_us == 10_000_000
    assert result.recovery_timeout_us == 60_000_000
    assert len(result.policy_id) == 64
    assert os.environ == before
    assert policy.resolve(dict(reversed(list(document().items())))).policy_id == result.policy_id


@pytest.mark.parametrize("field", policy.FLOAT_FIELDS + policy.INT_FIELDS + policy.TIMEOUT_FIELDS)
def test_changed_numeric_inputs_change_audit_identity_or_are_rejected(tmp_path, field):
    original = document()
    changed = deepcopy(original)
    target = changed if field in policy.TIMEOUT_FIELDS else changed["api_settings"]
    target[field] += .01 if "probability" in field or "confluence" in field else 1
    if field == "maximum_open_positions":
        with pytest.raises(ValueError):
            policy.resolve(changed)
        return
    a, b = policy.resolve(original), policy.resolve(changed)
    assert a.policy_id != b.policy_id
    first, second = runtime(a, tmp_path / "a"), runtime(b, tmp_path / "b")
    # Preserve the existing risk identity contract: API fields/timeouts are not
    # in NativeAccountSafetyV3's ArmsSettings digest. Audit ID covers them all.
    assert first.lifecycle.native_admission_producer_v3.risk_version() == second.lifecycle.native_admission_producer_v3.risk_version()
    assert original == document()


@pytest.mark.parametrize("field", ["schema", "version", "api_settings", *policy.TIMEOUT_FIELDS, *policy.FLOAT_FIELDS, *policy.INT_FIELDS])
def test_missing_fields_rejected(field):
    value = document()
    target = value["api_settings"] if field in policy.FLOAT_FIELDS + policy.INT_FIELDS else value
    del target[field]
    with pytest.raises(ValueError):
        policy.resolve(value)


@pytest.mark.parametrize("where", ["root", "api"])
def test_unknown_fields_rejected(where):
    value = document()
    (value if where == "root" else value["api_settings"])["unexpected"] = 1
    with pytest.raises(ValueError):
        policy.resolve(value)


@pytest.mark.parametrize("field,bad", [("schema", "wrong"), ("version", 2), ("version", True), ("version", 1.0)])
def test_wrong_identity_rejected(field, bad):
    value = document(); value[field] = bad
    with pytest.raises(ValueError):
        policy.resolve(value)


@pytest.mark.parametrize("field", policy.FLOAT_FIELDS + policy.INT_FIELDS + policy.TIMEOUT_FIELDS)
@pytest.mark.parametrize("bad", [True, False, float("nan"), float("inf"), float("-inf"), "1"])
def test_invalid_numeric_types_rejected(field, bad):
    value = document()
    (value if field in policy.TIMEOUT_FIELDS else value["api_settings"])[field] = bad
    with pytest.raises(ValueError):
        policy.resolve(value)


@pytest.mark.parametrize("field,bad", [("maximum_open_positions", 2), ("maximum_open_positions", 0),
    ("recovery_timeout_us", 10_000_000), ("recovery_timeout_us", 1), ("protection_timeout_us", 0),
    ("minimum_stop_points", 101), ("minimum_a_plus_probability", 1.1), ("minimum_a_plus_confluence_score", -1)])
def test_invalid_bounds_rejected(field, bad):
    value = document()
    (value if field in policy.TIMEOUT_FIELDS else value["api_settings"])[field] = bad
    with pytest.raises(ValueError):
        policy.resolve(value)


def test_duplicate_json_rejected(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text('{"version":1,' + policy.POLICY_PATH.read_text().lstrip()[1:])
    with pytest.raises(ValueError, match="duplicate"):
        policy.load(path)


def test_float_conversion_overflow_rejected():
    value = document()
    value["api_settings"]["maximum_quote_age_seconds"] = 10 ** 400
    with pytest.raises(ValueError, match="overflow"):
        policy.resolve(value)


def test_paper_live_profile_environment_and_safety_unchanged(tmp_path):
    from backend.services.runtime_context_v2 import build_runtime_context
    environment = dict(os.environ)
    api_before = asdict(APISettings())
    registry = AccountRegistryV1()
    profiles = {name: asdict(registry.get_account(name)) for name in registry.list_accounts()}
    paper_before = build_runtime_context()
    selected = policy.load()
    native = runtime(selected, tmp_path)
    paper_after = build_runtime_context()
    assert asdict(paper_before.settings) == asdict(paper_after.settings)
    assert paper_before.execution_manager.execution_mode == paper_after.execution_manager.execution_mode == "PAPER"
    assert asdict(APISettings()) == api_before
    assert os.environ == environment
    assert {name: asdict(registry.get_account(name)) for name in registry.list_accounts()} == profiles
    assert native.binding.execution_domain == "SIM_NATIVE"
    assert native.binding.execution_capability == "DISABLED"
    assert not native.store._durability.enabled
    root = Path(__file__).resolve().parents[2]
    source = (root / "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs").read_text()
    for flag in ("NATIVE_SUBMIT_ENABLED", "AUTO_RETRY_ALLOWED"):
        assert re.search(r"const\s+bool\s+" + flag + r"\s*=\s*false\s*;", source)
    assert not list(tmp_path.iterdir())


def test_explicit_cli_publishes_from_policy_without_ten_environment_values(isolated, monkeypatch, capsys):
    root, identity, protected = isolated
    for name in policy.FLOAT_FIELDS + policy.INT_FIELDS:
        monkeypatch.delenv("ARMS_" + name.upper(), raising=False)
    before = dict(os.environ)
    builder = operator.build_native_sim_runtime
    captured = []
    def build(**kwargs):
        result = builder(**kwargs)
        captured.append(result)
        return result
    monkeypatch.setattr(operator, "build_native_sim_runtime", build)
    operator.main(["--commissioning-policy-v1", "--configuration-generation", "1"])
    evidence = json.loads(capsys.readouterr().out)
    assert evidence["commissioning_policy_id"] == policy.load().policy_id
    values = evidence["configuration"]
    assert "commissioning_policy_id" not in values
    assert values["authority_id"] == identity
    producer = captured[0].lifecycle.native_admission_producer_v3
    assert values["risk_version"] == producer.risk_version()
    assert producer.protection_timeout_us == 10_000_000
    assert producer.recovery_timeout_us == 60_000_000
    assert (root / "authority.dpapi").read_bytes() == protected
    assert os.environ == before
    assert not captured[0].store._durability.enabled
    assert all(not list(path.iterdir()) for path in operator.canonical_paths().values())


def test_policy_cli_rejects_overrides():
    with pytest.raises(SystemExit) as error:
        operator.main(["--commissioning-policy-v1", "--configuration-generation", "1", "--protection-timeout-us", "1"])
    assert error.value.code == 2
