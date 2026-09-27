"""Real DPAPI in isolated temporary directories, synthetic SDK mutation counters."""
import hashlib
import hmac
import json
from pathlib import Path

import pytest

from backend.services import sim_native_authority_v3 as auth
from backend.tests.test_sim_native_integration_v3 import bridge_binary, artifacts, run_bridge
from backend.tests.test_controlled_sim_operation_v3 import BINDING, KEY, NOW


def setup(root, *, existing_key=None):
    for name in ("spool/commands", "activation", "state", "receipts", "authority"):
        (root / name).mkdir(parents=True, exist_ok=True)
    authority = root / "authority"
    if existing_key is None:
        identity = auth.provision_authority(authority)
    else:
        # Only protected fixture key bytes are written by these new tests.
        (authority / "authority.dpapi").write_bytes(auth.HEADER + auth.dpapi(existing_key, protect=True))
        identity = auth.authority_id(existing_key)
    paths = dict(zip(auth.PATH_FIELDS, (root/"spool/commands", root/"activation", root/"state", root/"receipts")))
    values = auth.publish_config(binding=BINDING, configuration_generation=1, risk_version="risk-v1",
        paths=paths, issued_us=NOW-1_000_000, expires_us=NOW+60_000_000, root=authority)
    pin_names = (*auth.PATH_FIELDS, "authority_id", "backend_account_id", "native_account", "provider",
                 "instrument", "runtime_generation", "configuration_generation", "execution_domain")
    pins = {k: values[k] for k in pin_names}
    (root/"pins.json").write_text(json.dumps(pins))
    return authority, values, pins, identity


def sign(root, values):
    raw = auth.canonical(values)
    (root/"controlled-v3-config.json").write_bytes(raw)
    (root/"controlled-v3-config.sig").write_text(hmac.new(auth.load_authority(root), auth.DOMAIN+raw, hashlib.sha256).hexdigest())


def assert_zero(result):
    assert [result[k] for k in ("create", "submit", "cancel", "flatten")] == [0, 0, 0, 0]


def test_backend_protect_native_unprotect_bootstrap_is_idempotent(bridge_binary, tmp_path):
    root, values, pins, identity = setup(tmp_path)
    protected_before = (root/"authority.dpapi").read_bytes()
    assert auth.provision_authority(root) == identity
    assert (root/"authority.dpapi").read_bytes() == protected_before
    result = run_bridge(bridge_binary, tmp_path, "bootstrap")
    assert result["configured"] is True, (tmp_path/"controlled-v3-commissioning-status.json").read_text()
    assert_zero(result)
    status = json.loads((tmp_path/"controlled-v3-commissioning-status.json").read_text())
    assert status["authority_id"] == hashlib.sha256(auth.load_authority(root)).hexdigest()
    assert status["config_signature_valid"] and status["controlled_v3_configured"]
    assert status["restore_status"] == "NO_PERSISTED_OPERATION"
    assert status["auto_retry_allowed"] is False
    key = auth.load_authority(root)
    for path in root.iterdir():
        if path.is_file():
            assert key not in path.read_bytes()
    assert key.hex() not in json.dumps(status)


@pytest.mark.parametrize("case", ["missing", "corrupt_dpapi", "wrong_user_equivalent", "fingerprint", "altered_config",
    "altered_signature", "another_authority", "schema", "generation", "stale", "future", "backend_account",
    "native_account", "provider", "instrument", "runtime_generation", "domain", "command_directory",
    "activation_directory", "state_directory", "reconciliation_directory", "signature_generation", "missing_directory",
    "duplicate_field", "null_field", "restore_corrupt", "version", "issued_at"])
def test_bootstrap_negative_controls(bridge_binary, tmp_path, case):
    root, values, pins, _ = setup(tmp_path)
    mapping = {"schema":"schema", "generation":"configuration_generation", "backend_account":"backend_account_id",
               "domain":"execution_domain", "fingerprint":"authority_id"}
    if case == "missing":
        (root/"authority.dpapi").unlink()
    elif case in {"corrupt_dpapi", "wrong_user_equivalent"}:
        blob = (root/"authority.dpapi").read_bytes()
        (root/"authority.dpapi").write_bytes(blob[:-1] + bytes([blob[-1] ^ 1]))
    elif case == "another_authority":
        (root/"authority.dpapi").write_bytes(auth.HEADER+auth.dpapi(bytes(reversed(range(32))), protect=True))
    elif case in {"altered_signature", "signature_generation"}:
        (root/"controlled-v3-config.sig").write_text("0"*64)
    elif case == "altered_config":
        (root/"controlled-v3-config.json").write_bytes(auth.canonical({**values, "provider":"Other"}))
    elif case == "missing_directory":
        (tmp_path/"receipts").rmdir()
    elif case == "restore_corrupt":
        (tmp_path/"state/00000001.state").write_text("uncertain")
    elif case in {"duplicate_field", "null_field"}:
        raw = auth.canonical(values)
        if case == "duplicate_field":
            raw = b'{"schema":"ignored",' + raw[1:]
        else:
            raw = raw.replace(b'"risk_version":"risk-v1"', b'"risk_version":null')
        (root/"controlled-v3-config.json").write_bytes(raw)
        (root/"controlled-v3-config.sig").write_text(hmac.new(auth.load_authority(root), auth.DOMAIN+raw, hashlib.sha256).hexdigest())
    else:
        key = mapping.get(case, case)
        if case == "stale":
            key, value = "expires_us", str(NOW)
        elif case == "future":
            key, value = "issued_us", str(NOW+1)
        else:
            value = values[key]+"-wrong"
        values[key] = value
        sign(root, values)
    result = run_bridge(bridge_binary, tmp_path, "bootstrap")
    assert result["configured"] is False
    assert_zero(result)
    status = json.loads((tmp_path/"controlled-v3-commissioning-status.json").read_text())
    assert status["controlled_v3_configured"] is False
    assert status["last_configuration_error"]
    if case == "missing":
        assert not (root/"authority.dpapi").exists()


def test_load_missing_never_provisions(tmp_path):
    with pytest.raises(FileNotFoundError):
        auth.load_authority(tmp_path/"absent")
    assert not (tmp_path/"absent").exists()


def test_unprotect_failure_is_not_repaired_or_rotated(tmp_path):
    tmp_path = tmp_path / "authority"
    auth.provision_authority(tmp_path)
    target = tmp_path/"authority.dpapi"
    target.write_bytes(auth.HEADER+b"wrong-user-or-corrupt")
    before = target.read_bytes()
    with pytest.raises(ValueError):
        auth.provision_authority(tmp_path)
    assert target.read_bytes() == before


@pytest.mark.parametrize("mode", ["entry", "b2_unknown_before_entry"])
def test_bootstrap_restore_preserves_uncertainty_and_fence(bridge_binary, tmp_path, mode):
    artifacts(tmp_path)
    run_bridge(bridge_binary, tmp_path, mode)
    before = {p.name:p.read_bytes() for p in (tmp_path/"activation").iterdir()}
    setup(tmp_path, existing_key=KEY)
    result = run_bridge(bridge_binary, tmp_path, "restore_bootstrap")
    assert result["configured"] is True
    assert_zero(result)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert before == {p.name:p.read_bytes() for p in (tmp_path/"activation").iterdir()}
    assert json.loads((tmp_path/"controlled-v3-commissioning-status.json").read_text())["reconciliation_fence"] is True


def test_configuration_generation_cannot_be_reused_or_rolled_back(tmp_path):
    root, values, _, _ = setup(tmp_path)
    kwargs = dict(binding=BINDING, configuration_generation=1, risk_version="risk-v1",
        paths={k:values[k] for k in auth.PATH_FIELDS}, issued_us=NOW-1_000_000, expires_us=NOW+60_000_000, root=root)
    assert auth.publish_config(**kwargs) == values
    with pytest.raises(ValueError, match="generation"):
        auth.publish_config(**{**kwargs, "expires_us":NOW+70_000_000})
    assert not (root/"configuration-publish.lock").exists()


def test_authority_locations_reject_repository_cloud_custom(tmp_path):
    for path in (Path(__file__).resolve().parents[2]/"authority", tmp_path/"OneDrive"/"authority", tmp_path/"Custom"/"authority"):
        with pytest.raises(ValueError):
            auth.provision_authority(path)
        assert not path.exists()


def test_manual_fence_is_observed_without_cancel_or_flatten(bridge_binary, tmp_path):
    artifacts(tmp_path)
    run_bridge(bridge_binary, tmp_path, "manual_no_permit")
    fences = {p.name:p.read_bytes() for p in (tmp_path/"activation").glob("manual-reconciliation-*.pending")}
    assert fences
    setup(tmp_path, existing_key=KEY)
    result = run_bridge(bridge_binary, tmp_path, "restore_bootstrap")
    assert result["configured"] is True
    assert_zero(result)
    status = json.loads((tmp_path/"controlled-v3-commissioning-status.json").read_text())
    assert status["restore_status"] == "MANUAL_RECONCILIATION_REQUIRED"
    assert status["reconciliation_fence"] is True
    assert fences == {p.name:p.read_bytes() for p in (tmp_path/"activation").glob("manual-reconciliation-*.pending")}


def test_production_factory_loads_canonical_authority_only(monkeypatch):
    from backend.services import sim_native_runtime_v3 as runtime
    calls = []
    monkeypatch.setattr(auth, "load_authority", lambda: calls.append("load") or b"x"*32)
    monkeypatch.setattr(runtime, "build_native_sim_runtime", lambda **kwargs: kwargs)
    assert runtime.build_provisioned_native_sim_runtime(binding=BINDING)["authority_key"] == b"x"*32
    assert calls == ["load"]
    for override in ({"authority_key":b"other"}, {"authority_root":"other"}):
        with pytest.raises(ValueError):
            runtime.build_provisioned_native_sim_runtime(**override)
    assert calls == ["load"]


def test_interrupted_configuration_publication_fails_closed(bridge_binary, tmp_path, monkeypatch):
    root, values, _, _ = setup(tmp_path)
    atomic = auth._atomic
    def interrupted(path, data, **kwargs):
        if path.suffix == ".sig":
            raise OSError("synthetic interrupted signature publication")
        return atomic(path, data, **kwargs)
    monkeypatch.setattr(auth, "_atomic", interrupted)
    with pytest.raises(OSError):
        auth.publish_config(binding=BINDING, configuration_generation=2, risk_version="risk-v1",
            paths={k:values[k] for k in auth.PATH_FIELDS}, issued_us=NOW, expires_us=NOW+60_000_000, root=root)
    result = run_bridge(bridge_binary, tmp_path, "bootstrap")
    assert not result["configured"]
    assert_zero(result)


def test_private_authority_directory_acl(tmp_path):
    import subprocess
    root = tmp_path/"authority"
    auth.provision_authority(root)
    # Path is a pytest-generated local path, not a user supplied shell fragment.
    escaped = str(root).replace("'", "''")
    script = "$a=Get-Acl -LiteralPath '"+escaped+"';[pscustomobject]@{protected=$a.AreAccessRulesProtected;sids=@($a.Access|%{$_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value});owner=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value}|ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True)
    assert result.returncode == 0
    acl = json.loads(result.stdout)
    assert acl["protected"] is True
    assert set(acl["sids"]) == {acl["owner"], "S-1-5-18"}
