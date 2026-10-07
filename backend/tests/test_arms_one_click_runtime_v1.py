"""Offline-only tests for ARMS One-Click Runtime V1 Phase 1."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from backend.config.api_settings import APISettings
import tools.arms_one_click_runtime_v1 as runtime


NOW = datetime(2026, 10, 6, 18, 30, tzinfo=timezone.utc)
IDENTITY = UUID("12345678-1234-5678-9abc-def012345678")


def _write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": str(path), "sha256": sha256(raw).hexdigest()}


def _fixture(tmp_path):
    inputs = tmp_path / "inputs"
    python = inputs / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_bytes(b"offline-test-python")
    spec = json.dumps({
        "schema": "arms.native-capture-spec.sprint13.v1",
        "unknown_policy": "FAIL_CLOSED", "order_authority": False,
    }).encode()
    profile = {
        "schema": runtime.PROFILE_SCHEMA, "mode": "OFFLINE_ONLY",
        "execution_authority": False, "live_authority": False,
        "external_order_authority": False, "python_path": str(python),
        "installed_exporter": _write(inputs / "exporter.cs", b"read-only"),
        "bootstrap_evidence": _write(inputs / "bootstrap.json", b"{}"),
        "startup_chart_catchup_source": _write(
            inputs / "catchup.cs", b"read-only catchup"),
        "native_spec": _write(inputs / "native-spec.json", spec),
        "paper_config": _write(inputs / "paper-config.json", b"{}"),
        "runtime_parent": str(tmp_path / "destinations" / "analysis"),
        "paper_namespace_parent": str(tmp_path / "destinations" / "paper"),
        "news_parent": str(tmp_path / "destinations" / "news"),
        "l1_parent": str(tmp_path / "destinations" / "l1"),
        "ports": {"backend": 54000, "frontend": 54001, "paper": 54002},
        "admin_token_env": "ARMS_TEST_ADMIN_TOKEN",
        "startup_chart_catchup_timeout_seconds": 900,
    }
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    return SimpleNamespace(
        profile=profile, profile_path=profile_path,
        workspace=tmp_path / "plans",
        active=tmp_path / "active-runtime-sentinel")


def _reviewed_fixture(tmp_path):
    fixture = _fixture(tmp_path)
    inputs = tmp_path / "inputs"
    native_spec = json.dumps({
        "schema": "arms.native-capture-spec.sprint13.v1",
        "provider_enum": "Provider31", "expiry": "2026-12-01",
        "contract": {
            "provider": "Provider31", "instrument": "NQ",
            "contract": "NQ DEC26",
            "trading_hours_template": "CME US Index Futures ETH",
        },
        "unknown_policy": "FAIL_CLOSED", "order_authority": False,
    }).encode()
    fixture.profile["native_spec"] = _write(
        inputs / "native-spec.json", native_spec)
    fixture.profile["paper_config"] = _write(
        inputs / "paper-config.json",
        json.dumps(runtime.REVIEWED_PAPER_CONFIG).encode())
    fixture.profile.update({
        "reviewed_profile_version": runtime.REVIEWED_PROFILE_VERSION,
        "future_runtime_execution_enabled": False,
        "python_identity": {
            **runtime.REVIEWED_PYTHON_IDENTITY,
            "sha256": sha256(
                Path(fixture.profile["python_path"]).read_bytes()).hexdigest(),
        },
        "market_identity": dict(runtime.REVIEWED_MARKET_IDENTITY),
        "risk_and_execution_parameters":
            dict(runtime.REVIEWED_RISK_AND_EXECUTION),
        "runtime_environment": dict(runtime.REVIEWED_RUNTIME_ENVIRONMENT),
        "private_acl_required": True,
        "excluded_active_run_ids": [
            "20261006T171457Z-r24c-r13-992631f4"],
    })
    destinations = tmp_path / "reviewed-destinations"
    external = tmp_path.parent / (tmp_path.name + "-external-private")
    placeholder = "{RUN_ID}"
    fixture.profile["runtime_parent"] = str(destinations / "analysis")
    fixture.profile["paper_namespace_parent"] = str(destinations / "paper")
    fixture.profile["news_parent"] = str(external / "news")
    fixture.profile["l1_parent"] = str(external / "l1")
    fixture.profile["path_templates"] = {
        "analysis_namespace": str(
            destinations / "analysis" / placeholder),
        "market_inbox": str(
            destinations / "analysis" / placeholder / "inbox"),
        "catchup_directory": str(
            destinations / "analysis" / placeholder / "chart-catchup"),
        "external_private_l1_root": str(
            external / "l1" / placeholder),
        "paper_run_namespace": str(
            destinations / "paper" / placeholder),
        "command_channel": str(
            destinations / "paper" / placeholder / "controller-command-v1"),
        "current_paper_news_root": str(
            external / "news" / placeholder),
        "runtime_evidence_directory": str(
            destinations / "evidence" / placeholder),
        "local_dumps": str(
            destinations / "evidence" / placeholder / "localdumps"),
    }
    pointer = tmp_path / "stable" / "current-plan.json"
    fixture.profile["stable_path_policy"] = {
        **runtime.REVIEWED_STABLE_PATH_POLICY,
        "pointer_path": str(pointer),
    }
    source_pins = {}
    for name in runtime.REVIEWED_SOURCE_NAMES:
        source_pins[name] = _write(
            inputs / "sources" / Path(name), ("source:" + name).encode())
    fixture.profile["reviewed_source_pins"] = source_pins
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    fixture.pointer = pointer
    fixture.external = external
    return fixture


def _prepare(fixture):
    fixture.active.write_text("DO NOT TOUCH", encoding="utf-8")
    result = runtime.prepare(
        fixture.profile_path, workspace=fixture.workspace,
        clock=lambda: NOW, identity=IDENTITY)
    return result, Path(result["run_directory"])


def _tree_snapshot(path):
    return {
        str(item.relative_to(path)): (item.stat().st_mtime_ns, item.read_bytes())
        for item in path.rglob("*") if item.is_file()
    }


def test_start_prepares_sealed_plan_without_execution_or_runtime_writes(tmp_path):
    fixture = _fixture(tmp_path)
    result, run = _prepare(fixture)
    assert result["state"] == runtime.PREPARED
    assert result["audit_status"] == "PASS"
    assert fixture.active.read_text() == "DO NOT TOUCH"
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["run_id"] == "20261006T183000Z-oneclick-123456781234"
    assert manifest["process_start_authority"] is False
    assert manifest["command_execution_performed"] is False
    assert manifest["admin_token"]["value_captured"] is False
    assert manifest["disabled_future_start_command"][:4] == [
        str(Path(fixture.profile["python_path"]).resolve()), "-B", "-m",
        "tools.windows_runtime_supervisor_v1",
    ]
    for key in ("supervisor_report_directory", "paper_run_namespace",
                "current_paper_news_root", "current_paper_l1_directory"):
        assert not Path(manifest["targets"][key]).exists()
    assert {item.name for item in run.iterdir()} == {
        "manifest.json", "seal.json", "events.json", "state.json"}


def test_status_and_audit_are_bit_for_bit_read_only(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    before = _tree_snapshot(tmp_path)
    assert runtime.status(run)["state"] == runtime.PREPARED
    audit = runtime.audit(run)
    assert audit["status"] == "PASS"
    assert audit["execution_started"] is False
    assert audit["process_control_performed"] is False
    assert _tree_snapshot(tmp_path) == before
    assert fixture.active.read_text() == "DO NOT TOUCH"


@pytest.mark.parametrize("mutation,reason", (
    (lambda p: p.update(live_authority=True),
     "OFFLINE_ZERO_AUTHORITY_REQUIRED"),
    (lambda p: p["ports"].update(frontend=p["ports"]["backend"]),
     "DISTINCT_BOUNDED_PORTS_REQUIRED"),
    (lambda p: p["native_spec"].update(sha256="0" * 64),
     "INPUT_SHA256_MISMATCH"),
))
def test_invalid_profiles_fail_closed_before_plan_creation(
        tmp_path, mutation, reason):
    fixture = _fixture(tmp_path)
    mutation(fixture.profile)
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match=reason):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


def test_native_spec_cannot_grant_order_authority(tmp_path):
    fixture = _fixture(tmp_path)
    spec_path = Path(fixture.profile["native_spec"]["path"])
    raw = json.dumps({
        "schema": "arms.native-capture-spec.sprint13.v1",
        "unknown_policy": "FAIL_CLOSED", "order_authority": True,
    }).encode()
    spec_path.write_bytes(raw)
    fixture.profile["native_spec"]["sha256"] = sha256(raw).hexdigest()
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(
            runtime.OfflineBlocked, match="FAIL_CLOSED_CONTRACT_REQUIRED"):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


def test_manifest_tamper_or_runtime_side_effect_blocks_readers(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["live_authority"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert runtime.status(run)["state"] == runtime.BLOCKED
    assert runtime.audit(run)["status"] == runtime.BLOCKED

    fixture2 = _fixture(tmp_path / "second")
    _, run2 = _prepare(fixture2)
    manifest2 = json.loads((run2 / "manifest.json").read_text())
    Path(manifest2["targets"]["paper_run_namespace"]).mkdir(parents=True)
    result = runtime.audit(run2)
    assert result["status"] == runtime.BLOCKED
    assert "RUNTIME_SIDE_EFFECT_DETECTED" in result["blocking_reasons"][0]


def test_resealed_arbitrary_command_is_still_rejected_semantically(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["disabled_future_start_command"] = ["malicious-executable"]
    raw = (json.dumps(manifest, sort_keys=True, indent=2,
                      allow_nan=False).encode() + b"\n")
    manifest_path.write_bytes(raw)
    digest = sha256(raw).hexdigest()
    seal_path = run / "seal.json"
    seal = json.loads(seal_path.read_text())
    seal["manifest_sha256"] = digest
    seal_path.write_text(json.dumps(seal), encoding="utf-8")
    state_path = run / "state.json"
    state = json.loads(state_path.read_text())
    state["manifest_sha256"] = digest
    state_path.write_text(json.dumps(state), encoding="utf-8")
    result = runtime.audit(run)
    assert result["status"] == runtime.BLOCKED
    assert "DISABLED_COMMAND_CONTRACT_INVALID" in result["blocking_reasons"][0]


def test_stop_only_closes_offline_plan_and_is_idempotent(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    stopped = runtime.stop(run, clock=lambda: NOW)
    assert stopped["state"] == runtime.STOPPED
    assert stopped["process_control_performed"] is False
    events = json.loads((run / "events.json").read_text())["events"]
    assert [event["transition"] for event in events] == [
        "OFFLINE_PLAN_PREPARED", "OFFLINE_PLAN_STOPPED"]
    before = _tree_snapshot(tmp_path)
    assert runtime.stop(run, clock=lambda: NOW)["state"] == runtime.STOPPED
    assert _tree_snapshot(tmp_path) == before
    assert fixture.active.read_text() == "DO NOT TOUCH"


def test_stop_refuses_tampered_namespace_without_changing_evidence(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    state_path = run / "state.json"
    state = json.loads(state_path.read_text())
    state["execution_started"] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
    before = _tree_snapshot(run)
    with pytest.raises(runtime.OfflineBlocked, match="STATE_PROJECTION_INVALID"):
        runtime.stop(run, clock=lambda: NOW)
    assert _tree_snapshot(run) == before
    assert fixture.active.read_text() == "DO NOT TOUCH"


def test_concurrent_stop_lock_is_not_removed_by_non_owner(tmp_path):
    fixture = _fixture(tmp_path)
    _, run = _prepare(fixture)
    lock = run / ".offline-stop.lock"
    lock.write_text("owned elsewhere", encoding="utf-8")
    before = _tree_snapshot(run)
    with pytest.raises(FileExistsError):
        runtime.stop(run, clock=lambda: NOW)
    assert lock.read_text(encoding="utf-8") == "owned elsewhere"
    assert _tree_snapshot(run) == before


def test_all_four_cli_commands_are_offline_and_machine_readable(
        tmp_path, capsys):
    fixture = _fixture(tmp_path)
    assert runtime.main([
        "start", "--profile", str(fixture.profile_path),
        "--workspace", str(fixture.workspace),
    ]) == 0
    prepared = json.loads(capsys.readouterr().out)
    run = prepared["run_directory"]
    assert prepared["state"] == runtime.PREPARED
    assert runtime.main(["status", "--run", run]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == runtime.PREPARED
    assert runtime.main(["audit", "--run", run]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"
    assert runtime.main(["stop", "--run", run]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == runtime.STOPPED


def test_cli_help_and_source_have_no_process_network_or_native_control(capsys):
    with pytest.raises(SystemExit) as stopped:
        runtime.main(["--help"])
    assert stopped.value.code == 0
    assert "offline preparation only" in capsys.readouterr().out
    source = Path(runtime.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import subprocess", "from subprocess", "os.kill", "Popen(",
        "import socket", "urllib", "requests", "SubmitOrder", "CreateOrder(",
    ):
        assert forbidden not in source


def test_reviewed_profile_seals_all_phase1b_invariants_without_path_reuse(
        tmp_path):
    fixture = _reviewed_fixture(tmp_path)
    fixture.pointer.parent.mkdir(parents=True)
    fixture.pointer.write_text("ACTIVE POINTER - DO NOT SWITCH", encoding="utf-8")
    pointer_before = fixture.pointer.read_bytes()
    result, run = _prepare(fixture)
    assert result["state"] == runtime.PREPARED
    assert result["profile_valid"] is True
    assert result["plan_sealed"] is True
    assert result["source_binding"] == "PASS"
    assert result["path_policy"] == "PASS"
    assert result["active_run_collision"] is False
    assert result["live_execution_allowed"] is False
    assert result["external_order_authority"] is False
    assert result["current_paper_run_touched"] is False
    assert result["ninjatrader_touched"] is False
    assert result["paper_enabled_by_this_task"] is False
    assert fixture.pointer.read_bytes() == pointer_before

    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["runtime_environment"] == (
        runtime.REVIEWED_RUNTIME_ENVIRONMENT)
    assert set(manifest["source_pins"]) == runtime.REVIEWED_SOURCE_NAMES
    assert "disabled_future_start_command" in manifest
    serialized = json.dumps(manifest["targets"])
    assert fixture.profile["excluded_active_run_ids"][0] not in serialized
    assert not Path(manifest["targets"]["paper_run_namespace"]).exists()
    assert not Path(manifest["targets"]["current_paper_l1_directory"]).exists()
    assert not Path(manifest["targets"]["supervisor_report_directory"]).exists()


def test_reviewed_source_drift_reports_exact_block_and_creates_no_plan(
        tmp_path, capsys):
    fixture = _reviewed_fixture(tmp_path)
    source = Path(next(iter(
        fixture.profile["reviewed_source_pins"].values()))["path"])
    source.write_bytes(source.read_bytes() + b"-drift")
    assert runtime.main([
        "start", "--profile", str(fixture.profile_path),
        "--workspace", str(fixture.workspace),
    ]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["profile_status"] == runtime.BLOCKED_SOURCE_DRIFT
    assert result["source_binding"] == runtime.BLOCKED_SOURCE_DRIFT
    assert result["plan_sealed"] is False
    assert not fixture.workspace.exists()


@pytest.mark.parametrize("mutation,reason", (
    (lambda p, root: p.update(private_acl_required=False),
     "PRIVATE_ACL_REQUIRED"),
    (lambda p, root: p["path_templates"].update(
        external_private_l1_root=str(
            runtime.REPO_ROOT / "private" / "{RUN_ID}")),
     "EXTERNAL_L1_MUST_BE_OUTSIDE_REPOSITORY"),
    (lambda p, root: p["path_templates"].update(
        analysis_namespace=str(
            root / "20261006T171457Z-r24c-r13-992631f4" / "{RUN_ID}")),
     "PATH_TEMPLATE_INVALID"),
))
def test_reviewed_path_and_acl_policy_fail_closed(
        tmp_path, mutation, reason):
    fixture = _reviewed_fixture(tmp_path)
    mutation(fixture.profile, tmp_path)
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match=reason):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


def test_whole_plan_publication_is_atomic_on_evidence_failure(
        tmp_path, monkeypatch):
    fixture = _reviewed_fixture(tmp_path)
    original = runtime._atomic_json
    calls = 0

    def fail_third_write(path, value, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise runtime.OfflineBlocked("INJECTED_PUBLICATION_FAILURE")
        return original(path, value, **kwargs)

    monkeypatch.setattr(runtime, "_atomic_json", fail_third_write)
    with pytest.raises(
            runtime.OfflineBlocked, match="INJECTED_PUBLICATION_FAILURE"):
        runtime.prepare(
            fixture.profile_path, workspace=fixture.workspace,
            clock=lambda: NOW, identity=IDENTITY)
    assert fixture.workspace.exists()
    assert list(fixture.workspace.iterdir()) == []


def test_reviewed_status_and_audit_are_read_only_and_report_required_fields(
        tmp_path):
    fixture = _reviewed_fixture(tmp_path)
    _, run = _prepare(fixture)
    before = _tree_snapshot(tmp_path)
    status = runtime.status(run)
    audited = runtime.audit(run)
    assert status["profile_valid"] is True
    assert status["plan_sealed"] is True
    assert status["source_binding"] == "PASS"
    assert status["path_policy"] == "PASS"
    assert audited["active_run_collision"] is False
    assert audited["current_paper_run_touched"] is False
    assert audited["ninjatrader_touched"] is False
    assert audited["ARMS_MAXIMUM_QUOTE_AGE_SECONDS"] == "30"
    assert audited["ARMS_MINIMUM_REWARD_RISK_RATIO"] == "2.0"
    assert audited["api_settings_binding"] == "PASS"
    assert audited["required_api_settings"] == (
        runtime.REVIEWED_RUNTIME_ENVIRONMENT)
    assert audited["frozen_policy_drift"] == "NONE"
    assert _tree_snapshot(tmp_path) == before


@pytest.mark.parametrize("mutation,reason", (
    (lambda p: p["market_identity"].update(provider="OtherProvider"),
     "MARKET_IDENTITY_INVALID"),
    (lambda p: p["risk_and_execution_parameters"].update(
        maximum_spread_points=5.25),
     "RISK_AND_EXECUTION_PARAMETERS_INVALID"),
    (lambda p: p["runtime_environment"].pop(
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS"),
     "RUNTIME_ENVIRONMENT_INVALID"),
    (lambda p: p["runtime_environment"].update(
        ARMS_MAXIMUM_QUOTE_AGE_SECONDS="31"),
     "RUNTIME_ENVIRONMENT_INVALID"),
    (lambda p: p.update(future_runtime_execution_enabled=True),
     "FUTURE_RUNTIME_EXECUTION_MUST_REMAIN_DISABLED"),
    (lambda p: p["stable_path_policy"].update(
        pointer_switch_during_active_run_allowed=True),
     "STABLE_PATH_POLICY_INVALID"),
))
def test_reviewed_identity_authority_and_risk_drift_fail_closed(
        tmp_path, mutation, reason):
    fixture = _reviewed_fixture(tmp_path)
    mutation(fixture.profile)
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match=reason):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


def test_reviewed_audit_blocks_source_drift_after_sealing(tmp_path):
    fixture = _reviewed_fixture(tmp_path)
    _, run = _prepare(fixture)
    source = Path(next(iter(
        fixture.profile["reviewed_source_pins"].values()))["path"])
    source.write_bytes(source.read_bytes() + b"-post-seal-drift")
    audited = runtime.audit(run)
    assert audited["status"] == runtime.BLOCKED
    assert audited["profile_status"] == runtime.BLOCKED_SOURCE_DRIFT
    assert audited["source_binding"] == runtime.BLOCKED_SOURCE_DRIFT
    assert audited["execution_started"] is False
    assert audited["current_paper_run_touched"] is False


@pytest.mark.parametrize(
    "missing_name", tuple(runtime.REVIEWED_RUNTIME_ENVIRONMENT))
def test_every_required_api_setting_must_be_explicitly_bound(
        tmp_path, missing_name):
    fixture = _reviewed_fixture(tmp_path)
    fixture.profile["runtime_environment"].pop(missing_name)
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match="RUNTIME_ENVIRONMENT_INVALID"):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


@pytest.mark.parametrize("malformed", ("", "nan", "-1", "unexpected"))
def test_malformed_required_api_setting_blocks(tmp_path, malformed):
    fixture = _reviewed_fixture(tmp_path)
    fixture.profile["runtime_environment"][
        "ARMS_MINIMUM_REWARD_RISK_RATIO"] = malformed
    fixture.profile_path.write_text(
        json.dumps(fixture.profile), encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match="RUNTIME_ENVIRONMENT_INVALID"):
        runtime.prepare(fixture.profile_path, workspace=fixture.workspace)
    assert not fixture.workspace.exists()


def test_explicit_canonical_api_settings_construct_without_ambient_defaults(
        monkeypatch):
    for name, value in runtime.REVIEWED_RUNTIME_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    settings = APISettings()
    assert settings.maximum_quote_age_seconds == 30
    assert settings.minimum_reward_risk_ratio == 2.0
    assert settings.minimum_stop_points == 1
    assert settings.maximum_stop_points == 100
    assert settings.maximum_spread_points == 5
    assert settings.minimum_atr_points == 1
    assert settings.minimum_a_plus_probability == 0.80
    assert settings.minimum_a_plus_confluence_score == 0.80
    assert settings.maximum_signal_age_seconds == 300
    assert settings.maximum_open_positions == 1


@pytest.mark.parametrize(
    "missing_name", tuple(runtime.REVIEWED_RUNTIME_ENVIRONMENT))
def test_api_settings_never_silently_defaults_required_policy(
        monkeypatch, missing_name):
    for name, value in runtime.REVIEWED_RUNTIME_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv(missing_name)
    with pytest.raises(ValueError, match=missing_name):
        APISettings()


def test_reviewed_existing_future_namespace_blocks_without_reuse(tmp_path):
    fixture = _reviewed_fixture(tmp_path)
    run_id = "20261006T183000Z-oneclick-123456781234"
    analysis = Path(
        fixture.profile["path_templates"]["analysis_namespace"].replace(
            "{RUN_ID}", run_id))
    analysis.mkdir(parents=True)
    sentinel = analysis / "historical-sentinel.txt"
    sentinel.write_text("IMMUTABLE", encoding="utf-8")
    with pytest.raises(runtime.OfflineBlocked, match="FRESH_DESTINATIONS_REQUIRED"):
        runtime.prepare(
            fixture.profile_path, workspace=fixture.workspace,
            clock=lambda: NOW, identity=IDENTITY)
    assert sentinel.read_text(encoding="utf-8") == "IMMUTABLE"
    assert not fixture.workspace.exists()
