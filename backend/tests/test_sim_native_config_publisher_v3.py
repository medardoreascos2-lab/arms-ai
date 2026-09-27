"""Isolated CurrentUser DPAPI; synthetic policy only, no native runtime."""
from dataclasses import asdict, replace
import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.accounts.sim_native_account_v3 import SimNativeAccountV3, digest
from backend.config_settings import ArmsSettings
from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_runtime_v3 import NativeAdmissionProducerV3
from tools import publish_sim_native_config_v3 as operator


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "another-user"))
    root = auth.authority_root()
    identity = auth.provision_authority()
    protected = (root / "authority.dpapi").read_bytes()
    monkeypatch.setattr(auth, "provision_authority", Mock(side_effect=AssertionError("implicit provisioning")))
    return root, identity, protected


def publish(generation=1):
    # These are test-only timeouts; the CLI supplies no production defaults.
    return operator.publish(configuration_generation=generation,
        protection_timeout_us=1_000_000, recovery_timeout_us=20_000_000)


def verify(values, now=None):
    binding = SimNativeAccountV3.load(execution_domain="SIM_NATIVE", provider="Simulator", native_account_name="Sim101")
    return auth.verify_config(binding=binding, paths=operator.canonical_paths(), risk_version=values["risk_version"],
        configuration_generation=int(values["configuration_generation"]),
        now_us=int(values["issued_us"]) if now is None else now)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_publish_reuses_authority_canonical_paths_policy_and_zero_execution(isolated, monkeypatch, capsys):
    root, identity, protected = isolated
    real_builder = operator.build_native_sim_runtime
    captured = []
    def build(**kwargs):
        runtime = real_builder(**kwargs)
        # A publisher must only compose: no startup, admissions, or transport.
        for owner, names in ((runtime.store, ("start", "record_admission")),
            (runtime.lifecycle.native_admission_producer_v3, ("produce",)),
            (runtime.lifecycle.broker_connector_v2, ("submit_order", "modify_order", "cancel_order", "close_position"))):
            for name in names:
                monkeypatch.setattr(owner, name, Mock(side_effect=AssertionError("execution side effect")))
        captured.append(runtime)
        return runtime
    monkeypatch.setattr(operator, "build_native_sim_runtime", build)
    operator.main(["--configuration-generation", "1", "--protection-timeout-us", "1000000", "--recovery-timeout-us", "20000000"])
    output = capsys.readouterr().out
    values = json.loads(output)
    runtime = captured[0]
    policy = runtime.store._durability.account_switch_safety.settings
    profile = runtime.manager.get_active_account()
    assert policy == replace(ArmsSettings(), account_balance=float(profile.account_size), risk_percent=profile.risk_percent)
    assert values["risk_version"] == digest({"profile": runtime.binding.risk_profile_digest, "policy": digest(asdict(policy))})
    assert values["risk_version"] == runtime.lifecycle.native_admission_producer_v3.risk_version()
    assert values["authority_id"] == identity
    assert values["configuration_generation"] == values["runtime_generation"] == "1"
    assert int(values["expires_us"]) - int(values["issued_us"]) == 86_400_000_000
    assert verify(values) == values
    paths = operator.canonical_paths()
    assert len(set(paths.values())) == 4
    assert {p.name for p in (root / "runtime").iterdir()} == {"commands", "activations", "state", "reconciliation"}
    assert all(p.parent == root / "runtime" and p.is_dir() and not list(p.iterdir()) for p in paths.values())
    assert (root / "authority.dpapi").read_bytes() == protected
    key = auth.load_authority()
    assert key.hex() not in output
    assert all(key not in data for data in snapshot(root).values())
    auth.provision_authority.assert_not_called()
    assert not runtime.store._durability.enabled


@pytest.mark.parametrize("generation", [0, -1, 2, True])
def test_first_generation_exactly_one_no_write(isolated, generation):
    root, _, _ = isolated
    before = snapshot(root)
    with pytest.raises(ValueError, match="generation"):
        publish(generation)
    assert snapshot(root) == before
    assert not (root / "runtime").exists()


@pytest.mark.parametrize("generation", [0, 1, 3])
def test_reuse_rollback_and_skip_fail_without_rewriting(isolated, generation):
    root, _, _ = isolated
    publish()
    before = snapshot(root)
    with pytest.raises(ValueError, match="generation"):
        publish(generation)
    assert snapshot(root) == before


def test_only_explicit_next_generation_renews(isolated):
    root, _, _ = isolated
    first = publish()
    before = snapshot(root)
    with pytest.raises(ValueError, match="expired"):
        verify(first, int(first["expires_us"]))
    assert snapshot(root) == before
    second = publish(2)
    assert second["configuration_generation"] == "2"
    assert second["runtime_generation"] == "1"
    assert verify(second) == second


@pytest.mark.parametrize("location", ["OneDrive", "Custom", "repo"])
def test_unsafe_localappdata_fails_before_any_write(tmp_path, monkeypatch, location):
    path = Path(__file__).resolve().parents[2] if location == "repo" else tmp_path / location
    monkeypatch.setenv("LOCALAPPDATA", str(path))
    with pytest.raises(ValueError):
        operator.canonical_paths()


def test_missing_authority_is_never_provisioned(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        publish()
    assert not (tmp_path / "ARMS-AI").exists()


def test_runtime_path_reparse_point_rejected(isolated, monkeypatch):
    root, _, _ = isolated
    paths = operator.canonical_paths()
    leaf = paths["command_directory"]
    leaf.mkdir(parents=True)
    real_lstat = Path.lstat
    monkeypatch.setattr(Path, "lstat", lambda path: SimpleNamespace(st_file_attributes=0x400)
                        if path == leaf else real_lstat(path))
    with pytest.raises(ValueError, match="redirected"):
        operator.canonical_paths()


@pytest.mark.parametrize("protection,recovery", [(0, 1), (1, 1), (2, 1), (True, 2)])
def test_invalid_timeout_policy_never_writes(isolated, protection, recovery):
    root, _, _ = isolated
    before = snapshot(root)
    with pytest.raises(ValueError, match="bounded recovery"):
        operator.publish(configuration_generation=1, protection_timeout_us=protection, recovery_timeout_us=recovery)
    assert snapshot(root) == before
    assert not (root / "runtime").exists()


def test_missing_policy_does_not_borrow_test_defaults(isolated, monkeypatch):
    root, _, _ = isolated
    monkeypatch.delenv("ARMS_MAXIMUM_QUOTE_AGE_SECONDS", raising=False)
    before = snapshot(root)
    with pytest.raises(ValueError, match="ARMS_MAXIMUM_QUOTE_AGE_SECONDS"):
        publish()
    assert snapshot(root) == before
    assert not (root / "runtime").exists()


def test_risk_disagreement_stops_before_writes(isolated, monkeypatch):
    root, _, _ = isolated
    before = snapshot(root)
    monkeypatch.setattr(NativeAdmissionProducerV3, "risk_version", lambda self: "wrong")
    with pytest.raises(ValueError, match="risk version"):
        publish()
    assert snapshot(root) == before
    assert not (root / "runtime").exists()


@pytest.mark.parametrize("field", ["schema", "version", "provider", "instrument", "backend_account_id", "risk_version", "issued_at", "state_directory"])
def test_authenticated_wrong_pins_rejected(isolated, field):
    root, _, _ = isolated
    values = publish()
    changed = {**values, field: values[field]+"-wrong"}
    raw = auth.canonical(changed)
    (root / "controlled-v3-config.json").write_bytes(raw)
    (root / "controlled-v3-config.sig").write_bytes(hmac.new(auth.load_authority(), auth.DOMAIN+raw, hashlib.sha256).hexdigest().encode())
    with pytest.raises(ValueError):
        verify(values)


@pytest.mark.parametrize("case", ["signature", "noncanonical", "duplicate", "torn"])
def test_corrupt_config_never_repaired_or_renewed(isolated, case):
    root, _, _ = isolated
    values = publish()
    raw = auth.canonical(values)
    if case == "torn":
        (root / "controlled-v3-config.sig").unlink()
    elif case == "signature":
        (root / "controlled-v3-config.sig").write_bytes(b"0"*64)
    else:
        raw = raw+b"\n" if case == "noncanonical" else b'{"schema":"wrong",'+raw[1:]
        (root / "controlled-v3-config.json").write_bytes(raw)
        (root / "controlled-v3-config.sig").write_bytes(hmac.new(auth.load_authority(), auth.DOMAIN+raw, hashlib.sha256).hexdigest().encode())
    before = snapshot(root)
    with pytest.raises((ValueError, OSError)):
        publish(2)
    assert snapshot(root) == before


def test_atomic_generation_check_rejects_concurrent_writer(isolated, monkeypatch):
    root, _, _ = isolated
    original = auth.publish_config
    competing = []
    def race(**kwargs):
        competing.append(original(**{**kwargs, "risk_version": "competing-valid-publisher"}))
        return original(**kwargs)
    monkeypatch.setattr(auth, "publish_config", race)
    with pytest.raises(ValueError, match="generation"):
        publish()
    assert auth.read_authenticated_config() == competing[0]


def test_cli_requires_explicit_runtime_timeouts(capsys):
    with pytest.raises(SystemExit) as failure:
        operator.main(["--configuration-generation", "1"])
    assert failure.value.code == 2
