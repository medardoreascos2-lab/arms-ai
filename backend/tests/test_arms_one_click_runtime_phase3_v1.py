"""Phase 3 sealed native-setup handoff and zero-authority regressions."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from uuid import UUID

import pytest

from backend.tests.test_arms_one_click_runtime_phase2_v1 import (
    FakeProcessAdapter, NATIVE_ID, NOW, _authorize as phase2_authorize,
    _fixture as phase2_fixture, _start as phase2_start,
)
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_phase3_v1 as phase3


SESSION_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


class FakeSetupAdapter:
    def __init__(self, mutate=None):
        self.calls = []
        self.mutate = mutate

    def apply_once(self, *, handoff):
        self.calls.append(deepcopy(handoff))
        receipt = {
            "schema": phase3.RECEIPT_SCHEMA,
            "run_id": handoff["run_id"],
            "native_runtime_id": handoff["runtime"]["native_runtime_id"],
            "native_session_id": SESSION_ID,
            "chart_contract": deepcopy(handoff["chart_contract"]),
            "settings": deepcopy(handoff["settings"]),
            "apply_count": 1,
            "applied_utc": NOW.isoformat().replace("+00:00", "Z"),
            **phase3._ZERO_AUTHORITY,
        }
        if self.mutate is not None:
            self.mutate(receipt)
        return receipt


class FakeHelloObserver:
    def __init__(self, values):
        self.values = list(values)

    def observe(self):
        return self.values.pop(0) if self.values else None


class FakeOperatorHelloObserver:
    def __init__(self, values):
        self.values = list(values)

    def observe_evidence(self):
        return self.values.pop(0) if self.values else None


class FakeTime:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, _seconds):
        self.value += 1.0


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path):
    fixture, run = phase2_fixture(tmp_path)
    fixture.active.write_text("DO NOT TOUCH", encoding="utf-8")
    authorization = phase2_authorize(run)
    phase2_start(run, authorization, FakeProcessAdapter())
    state = phase2.status(run)
    runtime = Path(state["native_setup"]["runtime_directory"])
    claim = json.loads((runtime / "claim.json").read_text(encoding="utf-8"))
    request = json.loads(
        (runtime / "chart-catchup-request.json").read_text(encoding="utf-8"))
    return fixture, run, runtime, claim, request, authorization


def _prepare(tmp_path, *, timeout=2):
    fixture, run, runtime, claim, request, phase2_authorization = _fixture(tmp_path)
    result = phase3.prepare_handoff(
        run, runtime, clock=lambda: NOW, hello_timeout_seconds=timeout)
    return fixture, run, runtime, claim, request, phase2_authorization, result


def _authorize(run, *, now=NOW, ttl=30):
    return phase3.authorize_setup(
        run, clock=lambda: now, ttl_seconds=ttl,
        token_factory=lambda _: b"s" * 32)


def _operator_authorize(run, *, now=NOW, ttl=30):
    return phase3.operator_authorization(
        run, clock=lambda: now, ttl_seconds=ttl,
        token_factory=lambda _: b"o" * 32)


def _hello_evidence(runtime_id=NATIVE_ID, provider="Provider31",
                    session=SESSION_ID):
    return {
        "native_session_id": session,
        "native_runtime_id": runtime_id,
        "provider": provider,
    }


def _active_hello(run, **overrides):
    handoff = phase3.status(run)["handoff"]
    control = json.loads(Path(
        handoff["native_binding"]["control_file"]).read_text(encoding="utf-8"))
    claim = json.loads(control["claim_json"])
    evidence = {
        **_hello_evidence(),
        "binding_nonce": claim["binding_nonce"],
        "binding_claim_sha256": control["claim_sha256"],
        "handoff_file_sha256": claim["handoff_file_sha256"],
    }
    evidence.update(overrides)
    return evidence


def _execute(run, authorization, adapter, observer, *, now=NOW):
    fake_time = FakeTime()
    return phase3.execute_authorized(
        run, authorization, authorization.token_for_immediate_consumption(),
        setup_adapter=adapter, hello_observer=observer,
        clock=lambda: now, monotonic=fake_time.monotonic,
        sleeper=fake_time.sleep)


def test_handoff_derives_exact_dynamic_paths_and_preserves_zero_authority(tmp_path):
    fixture, run, runtime, _, request, _, result = _prepare(tmp_path)
    handoff = result["handoff"]
    assert handoff["runtime"]["live_inbox"] == str((runtime / "inbox").resolve())
    assert handoff["runtime"]["catchup_output_directory"] == str(
        (runtime / "chart-catchup").resolve())
    assert handoff["runtime"]["from_close_utc"] == request["from_close_utc"]
    assert handoff["runtime"]["through_close_utc"] == "LATEST_CLOSED"
    assert handoff["chart_contract"] == phase3._CHART
    binding_file = Path(handoff["native_binding"]["control_file"])
    assert handoff["settings"]["ArmsReadOnlyMarketV1"] == {
        "OneClickBindingFile": str(binding_file),
        "OutputDirectory": "",
        "ExpectedProvider": "Provider31",
    }
    assert handoff["settings"]["ArmsChartCatchupBridgeV1"]["CaptureEnabled"] is True
    assert result["ninjatrader_setup_authority"] is False
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    assert phase2.status(run)["ninjatrader_control_authority"] is False
    assert json.loads(binding_file.read_text(encoding="utf-8"))["state"] == "REVOKED"
    assert fixture.active.read_text(encoding="utf-8") == "DO NOT TOUCH"


@pytest.mark.parametrize(("field", "value"), [
    ("output_directory", "C:/stale/previous-run/chart-catchup"),
    ("live_output_directory", "C:/stale/previous-run/inbox"),
    ("expected_provider_enum", "Provider32"),
    ("capture_enabled", False),
    ("through_close_utc", "2026-10-06T18:00:00Z"),
])
def test_invalid_or_stale_runtime_request_is_rejected(tmp_path, field, value):
    _, run, runtime, _, request, _ = _fixture(tmp_path)
    request[field] = value
    _write_json(runtime / "chart-catchup-request.json", request)
    with pytest.raises(phase3.Phase3Blocked, match="CHART_REQUEST_CONTRACT_INVALID"):
        phase3.prepare_handoff(run, runtime, clock=lambda: NOW)
    assert not (run / "phase3-handoff.json").exists()


def test_run_derived_from_close_is_bound_before_phase3_prepare(tmp_path):
    _, run, runtime, _, request, _ = _fixture(tmp_path)
    request["from_close_utc"] = "2026-10-06T17:39:00Z"
    _write_json(runtime / "chart-catchup-request.json", request)
    with pytest.raises(
            phase3.Phase3Blocked,
            match="PHASE2_NATIVE_SETUP_BINDING_MISMATCH"):
        phase3.prepare_handoff(run, runtime, clock=lambda: NOW)
    assert not (run / "phase3-handoff.json").exists()


@pytest.mark.parametrize("mutation", [
    lambda r: r["chart_contract"].update(instrument="ES DEC26"),
    lambda r: r["chart_contract"].update(bars_value=5),
    lambda r: r["chart_contract"].update(trading_hours="Default 24 x 7"),
    lambda r: r["chart_contract"].update(provider="Provider32"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        CaptureEnabled=False),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        FromCloseUtc="2026-10-06T17:39:00Z"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        ThroughCloseUtc="2026-10-06T18:00:00Z"),
    lambda r: r["settings"]["ArmsChartCatchupBridgeV1"].update(
        LiveOutputDirectory="C:/foreign/inbox"),
])
def test_apply_receipt_must_match_exact_chart_and_settings(tmp_path, mutation):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter(mutation)
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_APPLY_RECEIPT_INVALID"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))
    assert len(adapter.calls) == 1
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == 1
    assert state["ninjatrader_setup_authority"] is False


def test_exactly_one_apply_and_second_attempt_is_blocked(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter()
    result = _execute(
        run, authorization, adapter, FakeHelloObserver([None, SESSION_ID]))
    assert result["state"] == phase3.COMPLETE
    assert result["apply_count"] == len(adapter.calls) == 1
    assert result["ninjatrader_setup_authority"] is False
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_REQUIRED"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))
    assert len(adapter.calls) == 1


def test_operator_authorize_exposes_exact_sealed_values_and_zero_authority(
        tmp_path):
    _, run, runtime, _, _, _, _ = _prepare(tmp_path)
    result = _operator_authorize(run)
    assert result["state"] == phase3.AUTHORIZED
    assert result["apply_limit"] == 1
    assert result["chart_contract"] == phase3._CHART
    binding_file = Path(result["handoff"]["native_binding"]["control_file"]) if "handoff" in result else Path(phase3.status(run)["handoff"]["native_binding"]["control_file"])
    assert result["settings"]["ArmsReadOnlyMarketV1"] == {
        "OneClickBindingFile": str(binding_file),
        "OutputDirectory": "",
        "ExpectedProvider": "Provider31",
    }
    catchup = result["settings"]["ArmsChartCatchupBridgeV1"]
    assert catchup["CaptureEnabled"] is True
    assert catchup["OneClickBindingFile"] == str(binding_file)
    assert catchup["FromCloseUtc"] == ""
    assert catchup["ThroughCloseUtc"] == ""
    assert catchup["LiveOutputDirectory"] == ""
    assert result["ninjatrader_setup_authority"] is True
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    persisted = phase3.status(run)
    assert persisted["state"] == phase3.AUTHORIZED
    assert persisted["apply_count"] == 0
    serialized = (run / "phase3-events.json").read_text(encoding="utf-8")
    assert result["authorization_token"] not in serialized
    assert json.loads(binding_file.read_text(encoding="utf-8"))["state"] == "REVOKED"


def test_operator_attempt_is_recorded_before_hello_and_is_one_shot(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run)
    announcements = []

    class InspectingObserver:
        @staticmethod
        def observe_evidence():
            state = phase3.status(run)
            assert announcements
            assert announcements[0]["state"] == phase3.APPLYING
            assert announcements[0]["apply_count"] == 1
            assert state["state"] == phase3.AWAITING_HELLO
            assert state["apply_count"] == 1
            events = json.loads(
                (run / "phase3-events.json").read_text(encoding="utf-8"))[
                    "events"]
            assert phase3.APPLYING in [event["state"] for event in events]
            control = json.loads(Path(state["handoff"]["native_binding"]["control_file"]).read_text(encoding="utf-8"))
            assert control["state"] == "ACTIVE"
            claim = json.loads(control["claim_json"])
            runtime = state["handoff"]["runtime"]
            assert claim["runtime_directory"] == runtime["directory"]
            assert claim["live_inbox"] == runtime["live_inbox"]
            assert claim["catchup_output_directory"] == runtime["catchup_output_directory"]
            assert claim["apply_limit"] == 1
            assert all(claim[key] is False for key in phase3._ZERO_AUTHORITY)
            return _active_hello(run)

    result = phase3.begin_operator_apply(
        run, authorization["authorization_token"],
        authorization["handoff_file_sha256"],
        hello_observer=InspectingObserver(), clock=lambda: NOW,
        on_apply_recorded=announcements.append)
    assert result["state"] == phase3.COMPLETE
    assert result["apply_count"] == 1
    assert result["ninjatrader_setup_authority"] is False
    assert all(result[key] is False for key in phase3._ZERO_AUTHORITY)
    binding_file = Path(result["details"]["operator_attempt"]["binding_control_file"])
    assert json.loads(binding_file.read_text(encoding="utf-8"))["state"] == "REVOKED"
    with pytest.raises(phase3.Phase3Blocked,
                       match="SETUP_AUTHORIZATION_REQUIRED"):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=FakeOperatorHelloObserver([_hello_evidence()]),
            clock=lambda: NOW)


@pytest.mark.parametrize("evidence", [
    _hello_evidence(runtime_id="ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"),
    _hello_evidence(provider="Provider32"),
    _hello_evidence(session="not-a-session"),
])
def test_operator_foreign_hello_is_rejected_fail_closed(tmp_path, evidence):
    _, run, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run)
    with pytest.raises(phase3.Phase3Blocked):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=FakeOperatorHelloObserver([evidence]),
            clock=lambda: NOW)
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == 1
    assert state["ninjatrader_setup_authority"] is False


def test_operator_stale_hello_validation_failure_is_preserved(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run)

    class StaleHelloObserver:
        @staticmethod
        def observe_evidence():
            raise phase3.Phase3Blocked("PHASE3_NATIVE_HELLO_INVALID")

    with pytest.raises(phase3.Phase3Blocked,
                       match="PHASE3_NATIVE_HELLO_INVALID"):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=StaleHelloObserver(), clock=lambda: NOW)
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == 1


def test_operator_hello_timeout_preserves_failed_attempt_evidence(tmp_path):
    _, run, *_ = _prepare(tmp_path, timeout=1)
    authorization = _operator_authorize(run)
    timer = FakeTime()
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_HELLO_TIMEOUT"):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=FakeOperatorHelloObserver([]),
            clock=lambda: NOW, monotonic=timer.monotonic,
            sleeper=timer.sleep)
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == 1
    assert all(state[key] is False for key in phase3._ZERO_AUTHORITY)
    binding_file = Path(state["handoff"]["native_binding"]["control_file"])
    assert json.loads(binding_file.read_text(encoding="utf-8"))["state"] == "REVOKED"


@pytest.mark.parametrize("fault", [
    "stale_run", "expired", "runtime_id", "handoff_hash", "outside_parent",
    "traversal", "inbox_leaf", "catchup_leaf", "forged_field",
])
def test_fixed_binding_claim_faults_are_rejected(tmp_path, fault):
    _, run, runtime, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run)
    _, _, handoff, handoff_sha = phase3._load_handoff(run)
    state, _ = phase3._load_evidence(run, handoff)
    claim = phase3._binding_claim(
        handoff, handoff_sha, state["details"]["authorization"], NOW,
        b"n" * 32)
    check_time = NOW
    if fault == "stale_run":
        claim["one_click_run_id"] = "20261007T000000Z-oneclick-deadbeefdead"
    elif fault == "expired":
        check_time = NOW + timedelta(seconds=31)
    elif fault == "runtime_id":
        claim["native_runtime_id"] = "ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"
    elif fault == "handoff_hash":
        claim["handoff_file_sha256"] = "0" * 64
    elif fault == "outside_parent":
        claim["runtime_parent"] = str(runtime.parent.parent)
    elif fault == "traversal":
        claim["runtime_directory"] = str(runtime / ".." / runtime.name)
    elif fault == "inbox_leaf":
        claim["live_inbox"] = str(runtime / "chart-catchup")
    elif fault == "catchup_leaf":
        claim["catchup_output_directory"] = str(runtime / "inbox")
    else:
        claim["forged"] = True
    with pytest.raises(phase3.Phase3Blocked):
        phase3._validate_binding_claim(
            claim, handoff=handoff, handoff_file_sha=handoff_sha,
            now=check_time)


def test_prepare_does_not_overwrite_an_unexpired_active_binding(tmp_path):
    _, run, runtime, *_ = _fixture(tmp_path)
    _, manifest, *_ = phase3._load_context(run, require_waiting=True)
    binding_file = phase3._binding_file(manifest, create=True)
    _write_json(binding_file, {
        "schema": phase3.BINDING_CONTROL_SCHEMA,
        "state": "ACTIVE",
        "claim_json": json.dumps({
            "expires_utc": (NOW + timedelta(seconds=30)).isoformat(
            ).replace("+00:00", "Z")}),
        "claim_sha256": "0" * 64,
    })
    with pytest.raises(phase3.Phase3Blocked,
                       match="NATIVE_BINDING_ALREADY_ACTIVE"):
        phase3.prepare_handoff(run, runtime, clock=lambda: NOW)
    assert json.loads(binding_file.read_text(encoding="utf-8"))["state"] == "ACTIVE"


def test_begin_apply_cannot_overwrite_another_run_binding_owner(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run)
    binding_file = Path(
        phase3.status(run)["handoff"]["native_binding"]["control_file"])
    foreign = json.loads(binding_file.read_text(encoding="utf-8"))
    foreign["one_click_run_id"] = "20261007T000000Z-oneclick-deadbeefdead"
    _write_json(binding_file, foreign)
    with pytest.raises(phase3.Phase3Blocked,
                       match="NATIVE_BINDING_OWNERSHIP_MISMATCH"):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=FakeOperatorHelloObserver([]), clock=lambda: NOW)
    assert phase3.status(run)["state"] == phase3.FAILED
    assert json.loads(binding_file.read_text(encoding="utf-8"))[
        "one_click_run_id"] == foreign["one_click_run_id"]


def test_operator_authorization_expires_before_apply_attempt(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _operator_authorize(run, ttl=1)
    with pytest.raises(phase3.Phase3Blocked,
                       match="SETUP_AUTHORIZATION_EXPIRED"):
        phase3.begin_operator_apply(
            run, authorization["authorization_token"],
            authorization["handoff_file_sha256"],
            hello_observer=FakeOperatorHelloObserver([_hello_evidence()]),
            clock=lambda: NOW + timedelta(seconds=2))
    state = phase3.status(run)
    assert state["state"] == phase3.REVOKED
    assert state["apply_count"] == 0
    assert state["ninjatrader_setup_authority"] is False


def test_expired_authorization_is_consumed_relinquished_and_cannot_be_reused(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run, ttl=1)
    adapter = FakeSetupAdapter()
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_EXPIRED"):
        _execute(
            run, authorization, adapter, FakeHelloObserver([SESSION_ID]),
            now=NOW + timedelta(seconds=2))
    assert authorization.consumed is True
    assert adapter.calls == []
    state = phase3.status(run)
    assert state["state"] == phase3.REVOKED
    assert state["ninjatrader_setup_authority"] is False
    with pytest.raises(phase3.Phase3Blocked, match="SETUP_AUTHORIZATION_REQUIRED"):
        _execute(run, authorization, adapter, FakeHelloObserver([SESSION_ID]))


@pytest.mark.parametrize("target", ["source", "profile", "request"])
def test_source_config_or_request_digest_drift_blocks_before_apply(tmp_path, target):
    fixture, run, runtime, _, request, _, _ = _prepare(tmp_path)
    if target == "source":
        descriptor = fixture.profile["reviewed_source_pins"][phase3.PHASE3_SOURCE]
        Path(descriptor["path"]).write_bytes(b"drift")
    elif target == "profile":
        fixture.profile_path.write_text("{}", encoding="utf-8")
    else:
        request["from_close_utc"] = "2026-10-06T17:39:00Z"
        _write_json(runtime / "chart-catchup-request.json", request)
    with pytest.raises((phase3.Phase3Blocked, phase2.phase1.OfflineBlocked)):
        phase3.authorize_setup(run, clock=lambda: NOW)


def test_missing_hello_times_out_and_fails_closed_after_one_apply(tmp_path):
    _, run, *_ = _prepare(tmp_path, timeout=1)
    authorization = _authorize(run)
    adapter = FakeSetupAdapter()
    with pytest.raises(phase3.Phase3Blocked, match="NATIVE_HELLO_TIMEOUT"):
        _execute(run, authorization, adapter, FakeHelloObserver([]))
    state = phase3.status(run)
    assert state["state"] == phase3.FAILED
    assert state["apply_count"] == len(adapter.calls) == 1
    assert all(state[key] is False for key in phase3._ZERO_AUTHORITY)


def test_foreign_hello_session_is_rejected(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    authorization = _authorize(run)
    foreign = str(UUID("ffffffff-eeee-4ddd-8ccc-bbbbbbbbbbbb"))
    with pytest.raises(phase3.Phase3Blocked, match="FOREIGN_NATIVE_HELLO_SESSION"):
        _execute(
            run, authorization, FakeSetupAdapter(), FakeHelloObserver([foreign]))
    assert phase3.status(run)["state"] == phase3.FAILED


def test_status_rejects_tampered_authority_evidence(tmp_path):
    _, run, *_ = _prepare(tmp_path)
    events_path = run / "phase3-events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    events["events"][0]["order_authority"] = True
    _write_json(events_path, events)
    with pytest.raises(phase3.Phase3Blocked, match="PHASE3_EVENT_CHAIN_INVALID"):
        phase3.status(run)
