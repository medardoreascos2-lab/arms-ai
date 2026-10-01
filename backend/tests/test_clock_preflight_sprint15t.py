"""Offline proofs and characterization of unchanged runtime time checks.

All clock/reference/calendar inputs are SYNTHETIC. No native replays or accounts.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from tools.clock_preflight_v1 import (
    Interval, ReferenceBound, ReviewedBounds, Sample, WindowsState, OperationWindow,
    assess, boundary_proof, inside,
)
from backend.tests.test_current_paper_sprint10 import gate, event
from backend.tests.test_session_lifecycle_sprint12 import special_gate
from backend.market_data.session_state_v1 import SessionStateAuthorityV1
from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1

ERRORS_MS = [0, -10, 10, -50, 50, -100, 100, -150, 150, -250, 250, -1000, 1000]
BOUNDARIES_MS = [-1, 0, 1, 50, 150, 1000]
B = datetime(2026, 9, 21, 1, tzinfo=timezone.utc)
BUS = 60_000_000


def fixture_inputs(error_us=0, network_us=100):
    # Host = true UTC + error. These are explicit synthetic reviewed assumptions.
    refs = tuple(ReferenceBound(r,r,0,"SYNTHETIC_ONLY") for r in ("a","b"))
    bounds = ReviewedBounds("boot",0,10_000_000,0,0,refs,"SYNTHETIC_ONLY")
    samples = tuple(Sample(r,"boot",t+error_us,t+network_us+error_us,t,t+network_us,
                           t+network_us//2,t+network_us//2,True,True)
                    for r in ("a","b") for t in (1000,2000))
    return dict(samples=samples,bounds=bounds,
                windows=[OperationWindow("MARKET_ANALYSIS",Interval(0,1_000_000),False,"SYNTHETIC_ONLY")],
                windows_state=WindowsState("boot",2500,1000,True,True,"a","Hold",0),
                epoch="boot",host_now_us=3000+error_us,mono_now_us=3000)


@pytest.mark.parametrize("error_ms",ERRORS_MS)
def test_measured_offset_is_not_a_magic_acceptance_threshold(error_ms):
    result = assess(**fixture_inputs(error_ms*1000))
    assert result["utc_interval_us"] == [2950,3050]
    assert result["offset_interval_us"] == [-error_ms*1000-50,-error_ms*1000+50]
    assert result["clock_ready"]["MARKET_ANALYSIS"]
    assert not any(result["clock_ready"][op] for op in ("PAPER","NEWS","SIM","LIVE"))
    assert not result["runtime_readiness_granted"] and not result["execution_authority"]
    assert result["broker_order_calls"] == 0 and not result["account_access"]


@pytest.mark.parametrize("attack,reason",[
    ("no_bounds","REVIEWED_ERROR"), ("one_group","INDEPENDENT_REFERENCES"),
    ("single_sample","TWO_DISTINCT"), ("duplicate_samples","TWO_DISTINCT"),
    ("origin","INVALID_OR_UNTRUSTED"), ("unsynced_reference","INVALID_OR_UNTRUSTED"),
    ("old_sample","SAMPLE_AGE"), ("future_sample","SAMPLE_AGE"),
    ("epoch","UNREVIEWED_OR_CHANGED"), ("host_step","HOST_STEP"),
    ("disagreement","REFERENCE_DISAGREEMENT"), ("stale_sync","SYNC_FRESHNESS"),
    ("windows_error","WINDOWS_STATE"), ("stopped","WINDOWS_STATE"),
    ("horizon","BOUND_VALIDITY"), ("bool_integer","INVALID_INTEGER"),
    ("bad_window","INVALID_OPERATION_WINDOW"), ("missing_reference","TWO_DISTINCT"),
])
def test_unknown_never_grants_readiness(attack,reason):
    x=fixture_inputs()
    if attack=="no_bounds": x["bounds"]=None
    if attack=="one_group": x["bounds"]=replace(x["bounds"],references=tuple(replace(r,independence_group="same") for r in x["bounds"].references))
    if attack=="single_sample": x["samples"]=x["samples"][::2]
    if attack=="duplicate_samples": x["samples"]=(x["samples"][0],)*2+(x["samples"][2],)*2
    if attack=="origin": x["samples"]=tuple(replace(s,origin_verified=False) for s in x["samples"])
    if attack=="unsynced_reference": x["samples"]=tuple(replace(s,synchronized=False) for s in x["samples"])
    if attack=="old_sample":
        x["bounds"]=replace(x["bounds"],valid_from_mono_us=500)
        x["samples"]=(replace(x["samples"][0],mono_send_us=499),)+x["samples"][1:]
    if attack=="future_sample": x["samples"]=(replace(x["samples"][0],mono_receive_us=4000),)+x["samples"][1:]
    if attack=="epoch": x["epoch"]="reboot"
    if attack=="host_step": x["host_now_us"]+=1
    if attack=="disagreement": x["samples"]=tuple(replace(s,reference_receive_us=s.reference_receive_us+1000,reference_send_us=s.reference_send_us+1000) if s.reference=="b" else s for s in x["samples"])
    if attack=="stale_sync":
        x["bounds"]=replace(x["bounds"],valid_from_mono_us=500)
        x["windows_state"]=replace(x["windows_state"],last_sync_mono_us=0)
    if attack=="windows_error": x["windows_state"]=replace(x["windows_state"],last_error=2)
    if attack=="stopped": x["windows_state"]=replace(x["windows_state"],running=False)
    if attack=="horizon": x["horizon_us"]=10_000_000
    if attack=="bool_integer": x["mono_now_us"]=True
    if attack=="bad_window": x["windows"]*=2
    if attack=="missing_reference": x["samples"]=x["samples"][:2]
    result=assess(**x)
    assert result["status"]=="UNKNOWN"
    assert not any(result["clock_ready"].values())
    assert reason in result["reasons"][0]


def test_network_asymmetry_uses_full_causal_interval_and_hull():
    x=fixture_inputs(network_us=200)
    # Both peers can receive immediately with all delay on return path.
    x["samples"]=tuple(replace(s,reference_receive_us=s.mono_send_us,reference_send_us=s.mono_send_us) for s in x["samples"])
    result=assess(**x)
    assert result["utc_interval_us"]==[2800,3000]
    assert inside(Interval(3000,3000),Interval(*result["utc_interval_us"]))
    x["windows"]=[OperationWindow("MARKET_ANALYSIS",Interval(2900,3100),True,"fixture")]
    assert not assess(**x)["clock_ready"]["MARKET_ANALYSIS"]


def test_sample_age_drift_horizon_and_operation_boundaries():
    x=fixture_inputs()
    x["bounds"]=replace(x["bounds"],rate_error_ppb=1_000_000)
    x["windows"]=[OperationWindow("NEWS",Interval(0,3053),False,"fixture")]
    r=assess(**x)
    assert r["utc_interval_us"]==[2948,3053]
    assert not r["clock_ready"]["NEWS"]  # exact blackout boundary is excluded
    x["windows"]=[OperationWindow("NEWS",Interval(0,3053),True,"fixture")]
    assert assess(**x)["clock_ready"]["NEWS"]
    x["horizon_us"]=1
    assert not assess(**x)["clock_ready"]["NEWS"]
    x["mono_now_us"]=1_003_000; x["host_now_us"]=1_003_000
    r=assess(**x)
    assert r["utc_interval_us"][1]-r["utc_interval_us"][0]>2000
    assert not r["clock_ready"]["NEWS"]


@pytest.mark.parametrize("error_ms",ERRORS_MS)
@pytest.mark.parametrize("delay_ms",BOUNDARIES_MS)
@pytest.mark.parametrize("kind",["FORMING","CLOSED"])
def test_boundary_matrix_characterizes_runtime_and_independent_proof(error_ms,delay_ms,kind):
    g,clock=gate(B-timedelta(minutes=1),label="CLOSE"); g.connection(True)
    observed=B+timedelta(milliseconds=delay_ms+error_ms)
    clock[0]=observed
    label=B+(timedelta(minutes=1) if kind=="FORMING" else timedelta())
    e=event(0,B-timedelta(minutes=1),bar_time=label,event_time=observed,received_at=observed,
            kind="FORMING_CANDLE" if kind=="FORMING" else "CLOSED_CANONICAL_CANDLE")
    if delay_ms+error_ms<0:
        with pytest.raises(ValueError): g.admit(e)
        assert g.closed_count==0
    else:
        row=g.admit(e)
        assert g.closed_count==(kind=="CLOSED")
        if row: assert row.available_at==B
    # Exact synthetic true UTC shows the independent proof rejects future data
    # even where shared fast host timestamps pass the unchanged local comparisons.
    actual=BUS+delay_ms*1000
    proof=boundary_proof(kind=kind,close_label_us=BUS+(BUS if kind=="FORMING" else 0),
                         event_utc=Interval(actual,actual),receipt_utc=Interval(actual,actual),
                         now_utc=Interval(actual,actual),maximum_age_us=30_000_000)
    assert (proof=="PROVEN_TIME_CONDITIONS_ONLY")== (delay_ms>=0)


@pytest.mark.parametrize("error_ms",ERRORS_MS)
@pytest.mark.parametrize("true_age_us",[29_999_000,30_000_000,30_001_000])
def test_freshness_matrix_and_no_stale_proof(error_ms,true_age_us):
    g,clock=gate(B-timedelta(minutes=1),label="CLOSE");g.connection(True)
    h=B+timedelta(microseconds=true_age_us+error_ms*1000);clock[0]=h
    e=event(0,B-timedelta(minutes=1),bar_time=B,event_time=h,received_at=h)
    if true_age_us+error_ms*1000>30_000_000:
        with pytest.raises(ValueError):g.admit(e)
        assert g.closed_count==0
    else: assert g.admit(e).available_at==B
    true=BUS+true_age_us
    assert (boundary_proof(kind="CLOSED",close_label_us=BUS,event_utc=Interval(true,true),
        receipt_utc=Interval(true,true),now_utc=Interval(true,true),maximum_age_us=30_000_000)
        =="PROVEN_TIME_CONDITIONS_ONLY") == (true_age_us<=30_000_000)


@pytest.mark.parametrize("error_ms",ERRORS_MS)
@pytest.mark.parametrize("delay_ms",BOUNDARIES_MS)
def test_htf_labels_duplicates_and_incomplete_bucket_unchanged(error_ms,delay_ms):
    g,clock=gate(B);g.connection(True);htf=ClosedBarAggregatorV1()
    for n in range(60):
        e=event(n,B)
        h=e.event_time+timedelta(milliseconds=delay_ms+error_ms)
        clock[0]=h;e=replace(e,event_time=h,received_at=h)
        if delay_ms+error_ms<0:
            with pytest.raises(ValueError):g.admit(e)
            assert g.closed_count==0 and htf.emitted_counts=={"15m":0,"1h":0}
            return
        row=g.admit(e);htf.update_completed(row.candle())
        assert g.admit(e) is None
        assert htf.emitted_counts=={"15m":(n+1)//15,"1h":(n+1)//60}
    assert g.closed_count==g.duplicate_count==60
    assert htf.history("1h")[0].timestamp.astimezone(timezone.utc)==B
    e=event(61,B,sequence=60,event_id="60");clock[0]=e.event_time
    with pytest.raises(ValueError,match="RECOVERY_REQUIRED"):g.admit(e)
    assert htf.emitted_counts=={"15m":4,"1h":1}


@pytest.mark.parametrize("error_ms",ERRORS_MS)
@pytest.mark.parametrize("delay_ms",BOUNDARIES_MS)
@pytest.mark.parametrize("boundary,before,after",[
    ("2026-09-14T21:00:00+00:00","REOPENING","DAILY_MAINTENANCE"),
    ("2026-09-18T21:00:00+00:00","REOPENING","WEEKEND_CLOSED"),
    ("2026-09-20T22:00:00+00:00","WEEKEND_CLOSED","REOPENING"),
])
def test_session_boundary_clock_dependence(error_ms,delay_ms,boundary,before,after):
    b=datetime.fromisoformat(boundary);g,_=gate(b)
    authority=SessionStateAuthorityV1(g.market_hours)
    assert authority.resolve(b+timedelta(milliseconds=delay_ms+error_ms)).state == (before if delay_ms+error_ms<0 else after)
    # A symmetric uncertainty interval crossing the boundary cannot prove OPEN.
    interval=Interval(delay_ms*1000-abs(error_ms)*1000,delay_ms*1000+abs(error_ms)*1000)
    assert inside(interval,Interval(0,60_000_000),False)==(interval.low>=0)


@pytest.mark.parametrize("error_ms",ERRORS_MS)
def test_holiday_state_cannot_be_cleared_by_clock_preflight(error_ms):
    midday=B+timedelta(hours=12)
    g,_=special_gate(midday,closed=(midday.date(),))
    assert SessionStateAuthorityV1(g.market_hours).resolve(midday+timedelta(milliseconds=error_ms)).state=="HOLIDAY_CLOSED"
    x=fixture_inputs(error_ms*1000);x["windows"]=[]
    assert not any(assess(**x)["clock_ready"].values())


def test_unknown_uncertainty_and_current_host_are_not_grandfathered():
    evidence=json.loads(Path("backend/tests/clock_preflight_sprint15t.json").read_text())
    assert evidence["current_host"]["offset_estimate_us"]==[136893,138790]
    result=assess(**dict(fixture_inputs(-138000),bounds=None))
    assert result["status"]=="UNKNOWN" and not any(result["clock_ready"].values())
    assert not result["runtime_readiness_granted"]
    for op in ("MARKET_ANALYSIS","PAPER","NEWS","SIM","LIVE"):
        assert evidence["current_host"]["readiness"][op]=="UNKNOWN_INELIGIBLE"


def test_boundary_uncertainty_cannot_be_replaced_with_midpoint_or_grace():
    args=dict(kind="CLOSED",close_label_us=BUS,receipt_utc=Interval(BUS+1000,BUS+1000),
              now_utc=Interval(BUS+2000,BUS+2000),maximum_age_us=30_000_000)
    assert boundary_proof(**args,event_utc=Interval(BUS-1,BUS+1))=="UNKNOWN"
    assert boundary_proof(**args,event_utc=Interval(BUS,BUS))=="PROVEN_TIME_CONDITIONS_ONLY"
    assert boundary_proof(**dict(args,now_utc=Interval(BUS+30_000_000,BUS+30_000_001)),event_utc=Interval(BUS,BUS))=="UNKNOWN"


@pytest.mark.parametrize("outbound_us",[0,1,50,99,100])
@pytest.mark.parametrize("error_us",[-138000,0,138000])
def test_actual_time_is_inside_envelope_for_every_network_split(outbound_us,error_us):
    x=fixture_inputs(error_us)
    x["samples"]=tuple(replace(s,reference_receive_us=s.mono_send_us+outbound_us,
                               reference_send_us=s.mono_send_us+outbound_us) for s in x["samples"])
    r=assess(**x)
    assert inside(Interval(3000,3000),Interval(*r["utc_interval_us"]))
    for low,high in [(0,2999),(3001,4000),(0,4000)]:
        x["windows"]=[OperationWindow("MARKET_ANALYSIS",Interval(low,high),True,"fixture")]
        if assess(**x)["clock_ready"]["MARKET_ANALYSIS"]:
            assert low<=3000<=high


def test_wide_consistent_reference_cannot_be_discarded_to_improve_readiness():
    x=fixture_inputs()
    x["samples"]=tuple(replace(s,mono_send_us=s.mono_receive_us-1000,
        host_send_us=s.host_receive_us-1000,reference_receive_us=s.mono_receive_us-500,
        reference_send_us=s.mono_receive_us-500) if s.reference=="b" else s for s in x["samples"])
    x["windows"]=[OperationWindow("MARKET_ANALYSIS",Interval(2900,3100),True,"fixture")]
    r=assess(**x)
    assert r["utc_interval_us"]==[2500,3500]
    assert not r["clock_ready"]["MARKET_ANALYSIS"]


def test_runtime_and_historical_native_sources_match_reviewed_certificate():
    import hashlib
    cert=json.loads(Path("backend/tests/market_open_native_certification_sprint13.json").read_text())
    for path,digest in cert["reviewed_source_sha256"].items():
        # Production timing instrumentation is reviewed separately in Sprint 15W.
        # Do not silently extend the old native certificate to the new exporter.
        reviewed = Path(path)
        if path == "integrations/ninjatrader/ArmsReadOnlyMarketV1.cs":
            reviewed = Path("backend/tests/fixtures/ArmsReadOnlyMarketV1.sprint13.cs")
        if path == "backend/market_data/current_candle_authority_v1.py":
            reviewed = Path("backend/tests/fixtures/current_candle_authority_v1.sprint13.py")
        if path == "backend/backtesting/current_paper_runtime_v1.py":
            reviewed = Path("backend/tests/fixtures/current_paper_runtime_v1.sprint13.py")
        content=reviewed.read_text(encoding="utf-8").encode()
        assert hashlib.sha256(content).hexdigest()==digest, path


def test_current_paper_boundary_provenance_artifact_pins_offline_review_only():
    import hashlib

    artifact=json.loads(Path("backend/tests/current_paper_boundary_provenance_d4e4c.json").read_text(encoding="utf-8"))
    assert artifact["schema"] == "arms.current-paper-boundary-provenance.d4e4c.v1"
    assert artifact["status"] == "OFFLINE_FIX_REVIEW_PASS_LIVE_RERUN_PENDING"
    assert artifact["baseline_head"] == "22d7010a04a507e6dd82f0780c961d0b45c93e33"
    assert artifact["root_cause"] == "STRICT_CLOSED_BOUNDARY_TIMESTAMP_MISMATCH"
    assert artifact["real_run_id"] == "bfa05eaa-c88e-43c9-82e6-b2a11d52ec42"
    assert artifact["real_session"] == "23f0b820-f163-433d-94d2-1359399f70b7"
    assert artifact["real_failing_sequence"] == 67
    assert artifact["real_failing_bar_time"] == "2026-10-01T07:52:00.0000000Z"
    assert artifact["real_failing_event_time"] == "2026-10-01T07:51:59.9997804Z"
    assert artifact["real_boundary_offset_seconds"] == -0.0002196
    assert artifact["arbitrary_time_epsilon"] == artifact["event_time_mutation"] == "NONE"
    assert artifact["closure_proof"] == "CERTIFIED_NATIVE_SAME_CALLBACK_CLOSED"
    assert artifact["closure_proof_origin"] == "PRODUCTION_INTERNAL_CERTIFIED_NATIVE_HANDOFF_ONLY"
    assert artifact["received_after_close_required"] is True
    assert artifact["received_boundary_operator"] == ">="
    assert set(artifact["special_path_requirements"]) == {
        "CERTIFIED_STRUCTURAL_CLOSURE_PROVENANCE", "RECEIVED_AT_OR_AFTER_NOMINAL_CLOSE",
        "EXISTING_FRESHNESS", "EXISTING_SEQUENCE_CONTINUITY",
        "EXISTING_CONTRACT_WINDOW_AUTHORITY", "EXISTING_MARKET_HOURS_AUTHORITY",
        "EXISTING_OHLCV_VALIDATION",
    }
    assert artifact["live_rerun"] == "PENDING"
    for key in ("paper_auto_enable", "live_execution", "ninjatrader_account_access",
                "ninjatrader_order_authority"):
        assert artifact[key] is False
    assert artifact["proof_limit"] == "In-process object identity, not cryptographic attestation"
    assert artifact["bridge_diagnostic_inner_cause_preservation"] == "DEFERRED"

    expected_paths = {
        "backend/market_data/current_candle_authority_v1.py",
        "backend/backtesting/certified_native_paper_bridge_v1.py",
        "backend/tests/test_current_paper_sprint10.py",
        "backend/tests/test_certified_native_paper_bridge_v1.py",
    }
    assert set(artifact["source_sha256"]) == expected_paths
    assert "backend/tests/test_clock_preflight_sprint15t.py" not in artifact["source_sha256"]
    historical = {
        "backend/backtesting/certified_native_paper_bridge_v1.py":
            "backend/tests/fixtures/certified_native_paper_bridge_v1.d4e4c.py",
        "backend/tests/test_certified_native_paper_bridge_v1.py":
            "backend/tests/fixtures/test_certified_native_paper_bridge_v1.d4e4c.py",
        "backend/tests/test_current_paper_sprint10.py":
            "backend/tests/fixtures/test_current_paper_sprint10.d4e4c.py",
    }
    for path, digest in artifact["source_sha256"].items():
        reviewed = Path(historical.get(path, path))
        assert hashlib.sha256(reviewed.read_text(encoding="utf-8").encode()).hexdigest() == digest

    cert_path=Path(artifact["historical_sprint13_certificate"])
    cert=json.loads(cert_path.read_text(encoding="utf-8"))
    assert hashlib.sha256(cert_path.read_bytes()).hexdigest() == artifact["historical_sprint13_certificate_sha256"]
    historical_digest=cert["reviewed_source_sha256"]["backend/market_data/current_candle_authority_v1.py"]
    assert historical_digest == artifact["historical_sprint13_authority_sha256"]
    fixture=Path(artifact["historical_sprint13_authority_fixture"])
    assert hashlib.sha256(fixture.read_text(encoding="utf-8").encode()).hexdigest() == historical_digest


def test_current_paper_boundary_provenance_records_python_precision_limit():
    from backend.backtesting.certified_native_paper_bridge_v1 import _utc

    artifact=json.loads(Path("backend/tests/current_paper_boundary_provenance_d4e4c.json").read_text(encoding="utf-8"))
    source=artifact["real_failing_event_time"]
    parsed=_utc(source)
    assert parsed.isoformat() == artifact["timestamp_precision"]["parsed_real_failing_event_time"]
    assert parsed.isoformat() == "2026-10-01T07:51:59.999780+00:00"
    assert parsed < _utc(artifact["real_failing_bar_time"])
    assert artifact["timestamp_precision"]["exact_100ns_preservation"] is False
    assert artifact["timestamp_precision"]["precision_loss_is_special_path_authorization_basis"] is False
    assert artifact["arbitrary_time_epsilon"] == "NONE"


def test_current_paper_preboundary_defer_artifact_is_offline_only():
    import hashlib
    import shlex

    artifact = json.loads(Path(
        "backend/tests/current_paper_preboundary_defer_d4e5c2.json"
    ).read_text(encoding="utf-8"))
    assert artifact["schema"] == "arms.current-paper-preboundary-defer.d4e5c2.v1"
    assert artifact["status"] == "OFFLINE_FIX_REVIEW_PASS_LIVE_RERUN_PENDING"
    assert artifact["baseline_head"] == "42341c8ad828eed6eb80d7f84311acc1807948ba"
    assert artifact["third_run_id"] == "d2816b70-fb45-44be-901f-704d82af27f1"
    assert artifact["third_run_session"] == "6341cab9-6394-4f0b-9b32-9905c98b8a04"
    assert artifact["catchup_cutoff"] == "2026-10-01T14:22:00Z"
    assert artifact["paper_completed_observations"] == 2
    assert artifact["last_completed_canonical_time"] == "2026-10-01T14:24:00+00:00"
    assert artifact["next_candidate_native_sequence"] == 76
    assert artifact["next_candidate_bar_time"] == "2026-10-01T14:25:00.0000000Z"
    assert artifact["next_candidate_event_time"] == "2026-10-01T14:24:59.9062058Z"
    assert artifact["next_candidate_early_offset_ms"] == 93.7942
    assert artifact["early_delivery_poll_race"] == "PROVEN_POSSIBLE"
    assert artifact["exact_third_run_failure_attribution"] == "UNPROVEN_GENERIC_WRAPPER_ONLY"
    assert artifact["root_cause_confidence"] == "MEDIUM"
    assert artifact["authority_change"] == artifact["arbitrary_time_epsilon"] == "NONE"
    assert artifact["event_time_mutation"] == "NONE"
    assert artifact["received_at_semantics"] == "REAL_WALL_CLOCK_AT_ACTUAL_ADMISSION"
    assert artifact["pending_policy"] == "BOUNDED_FIFO_NO_OVERTAKE"
    assert artifact["pending_fifo_bound"] == 1024
    assert artifact["live_rerun"] == "PENDING"
    assert artifact["historical_899_exact_command"] == "NOT_RECOVERABLE"
    assert artifact["historical_899_result"] == "REPORTED_PREVIOUSLY"
    assert "not preserved in shell or log evidence" in artifact["historical_gate_limitation"]
    assert "for this D4E5C2 certification only" in artifact["historical_gate_limitation"]
    assert artifact["canonical_regression_version"] == "D4E5C2_CANONICAL_V1"
    modules = artifact["canonical_regression_modules"]
    assert len(modules) == 16 == len(set(modules))
    assert all(path.startswith("backend/tests/test_") and path.endswith(".py")
               and Path(path).is_file() for path in modules)
    command = artifact["canonical_regression_command"]
    args = shlex.split(command)
    assert args[:7] == [
        "python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "--basetemp=C:/Users/Thecrazyboss/AppData/Local/Temp/ARMS_D4E5C2R2_CANONICAL_V1_20261001",
    ]
    assert args[7:] == modules
    assert artifact["canonical_regression_environment"] == {
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
        "ARMS_MINIMUM_REWARD_RISK_RATIO": "2",
        "ARMS_MINIMUM_STOP_POINTS": "1",
        "ARMS_MAXIMUM_STOP_POINTS": "100",
        "ARMS_MAXIMUM_SPREAD_POINTS": "5",
        "ARMS_MINIMUM_ATR_POINTS": "1",
        "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.80",
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.80",
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
        "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_ADDOPTS": "",
    }
    assert artifact["canonical_regression_status"] == "PASS"
    assert artifact["canonical_regression_collected"] == 924
    assert artifact["canonical_regression_passed"] == 924
    assert artifact["canonical_regression_failed"] == 0
    assert artifact["canonical_regression_skipped"] == 0
    assert artifact["canonical_regression_warning_summary"] == (
        "1 StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` "
        "is deprecated; install `httpx2` instead."
    )
    assert artifact["canonical_regression_run_basis"] == "CURRENT_D4E5C2_WORKTREE"
    for key in ("paper_auto_enable", "live_execution", "ninjatrader_account_access",
                "ninjatrader_order_authority"):
        assert artifact[key] is False

    expected = {
        "backend/market_data/current_candle_authority_v1.py",
        "backend/backtesting/certified_native_paper_bridge_v1.py",
        "backend/tests/test_certified_native_paper_bridge_v1.py",
    }
    assert set(artifact["source_sha256"]) == expected
    assert "backend/tests/test_clock_preflight_sprint15t.py" not in expected
    assert artifact["source_sha256"] == {
        "backend/market_data/current_candle_authority_v1.py":
            "bcfe63f74c7d22880ed9d04288279743f92698273157d5944a7817db0c7f5561",
        "backend/backtesting/certified_native_paper_bridge_v1.py":
            "769d52ee42cda48875b6c1ff19489dbe7f81de799a12a9605590806981963158",
        "backend/tests/test_certified_native_paper_bridge_v1.py":
            "6f2f543a3a4d8d6fae6dc7e22ff7d7de211a95d6025b14975ab0b8cd165b97cc",
    }
    for path, digest in artifact["source_sha256"].items():
        assert hashlib.sha256(Path(path).read_text(encoding="utf-8").encode()).hexdigest() == digest

    historical = {
        "backend/tests/fixtures/certified_native_paper_bridge_v1.d4e4c.py":
            "backend/backtesting/certified_native_paper_bridge_v1.py",
        "backend/tests/fixtures/test_certified_native_paper_bridge_v1.d4e4c.py":
            "backend/tests/test_certified_native_paper_bridge_v1.py",
    }
    prior = json.loads(Path(
        "backend/tests/current_paper_boundary_provenance_d4e4c.json"
    ).read_text(encoding="utf-8"))
    assert set(artifact["historical_d4e4c_fixture_sha256"]) == set(historical)
    for fixture, former in historical.items():
        digest = hashlib.sha256(Path(fixture).read_text(encoding="utf-8").encode()).hexdigest()
        assert artifact["historical_d4e4c_fixture_sha256"][fixture] == digest
        assert prior["source_sha256"][former] == digest


def test_current_paper_preboundary_defer_live_artifact_certifies_ordered_no_execution():
    import hashlib
    from decimal import Decimal
    from tools.native_timing_witness_v1 import ticks

    artifact = json.loads(Path(
        "backend/tests/current_paper_preboundary_defer_d4e6_live.json"
    ).read_text(encoding="utf-8"))
    assert artifact["schema"] == "arms.current-paper-preboundary-defer.d4e6-live.v1"
    assert artifact["status"] == "LIVE_RERUN_PASS"
    assert artifact["baseline_head"] == "51c56d7cb99786530420e378050bfde71d9ba070"
    assert artifact["offline_certification_artifact"] == (
        "backend/tests/current_paper_preboundary_defer_d4e5c2.json"
    )
    offline_path = Path(artifact["offline_certification_artifact"])
    offline = json.loads(offline_path.read_text(encoding="utf-8"))
    assert offline["status"] == artifact["offline_certification_status"] == (
        "OFFLINE_FIX_REVIEW_PASS_LIVE_RERUN_PENDING"
    )
    assert hashlib.sha256(offline_path.read_bytes()).hexdigest() == (
        artifact["offline_certification_sha256"]
    ) == "c3f5ed89128d8d59af908e21d2373d3ea240634680682d20db1897f29b1c3a23"
    assert artifact["run_id"] == "dea7dc25-7e77-4e59-a8ab-f561c2f83973"
    assert artifact["native_session"] == "8fad5a2c-5257-4914-a33d-2f9737a9ea30"
    assert artifact["catchup_sha256"] == (
        "51779d20bd68088962ea9a05917d7efe234aaecb0527c71eda278f1e54b62a31"
    )
    assert artifact["catchup_bars"] == 9390
    assert artifact["catchup_cutoff"] == "2026-10-01T16:31:00.0000000Z"
    assert artifact["minimum_required_completed_closed"] == 5
    assert artifact["completed_closed_before_shutdown"] == 8
    assert artifact["source_observations_processed"] == 8
    assert artifact["last_completed_canonical_time"] == "2026-10-01T16:39:00+00:00"

    rows = artifact["closed_rows"]
    assert len(rows) == 8
    assert [row["bar_time"] for row in rows] == [
        f"2026-10-01T16:{minute:02d}:00.0000000Z" for minute in range(32, 40)
    ]
    assert [row["native_sequence"] for row in rows] == list(range(49, 148, 14))
    assert [row["callback_index"] for row in rows] == list(range(8012, 8020))
    assert all(row["same_callback_status"] == "PROVEN" for row in rows)
    offsets = []
    for row in rows:
        offset = Decimal(ticks(row["event_time"]) - ticks(row["bar_time"])) / 10000
        assert offset == Decimal(row["offset_ms"])
        offsets.append(offset)
    assert sum(offset < 0 for offset in offsets) == artifact["early_closed_count"] == 6
    assert sum(offset >= 0 for offset in offsets) == artifact["late_or_exact_closed_count"] == 2
    assert min(offsets) == Decimal(artifact["min_offset_ms"]) == Decimal("-113.5790")
    assert max(offsets) == Decimal(artifact["max_offset_ms"]) == Decimal("50.8621")
    assert artifact["same_callback_status"] == "PROVEN_FOR_ALL_EIGHT"
    assert artifact["live_fifo_proof"] == "PROVEN"
    assert artifact["preboundary_defer"] == "BOUNDED_FIFO"
    assert artifact["pending_fifo_bound"] == 1024
    assert artifact["fifo_no_overtake"] is True
    assert any("No transient pending FIFO snapshot" in item
               for item in artifact["proof_limitations"])

    assert artifact["received_at_semantics"] == "REAL_WALL_CLOCK_AT_ACTUAL_ADMISSION"
    assert artifact["authority_change"] == artifact["arbitrary_time_epsilon"] == "NONE"
    assert artifact["event_time_mutation"] == "NONE"
    for key in ("paper_auto_enable", "paper_execution_enabled", "paper_ready",
                "live_execution_allowed", "ninjatrader_account_access",
                "ninjatrader_order_authority", "order_submit_reachable_pre_shutdown",
                "runtime_failure_before_interrupt"):
        assert artifact[key] is False
    assert artifact["execution_state"] == "FLAT"
    assert artifact["journal_total"] == artifact["completed_trades"] == 0
    assert artifact["fault_detail"] is None
    assert artifact["shutdown_classification"] == "CONTROLLED_OPERATOR_INTERRUPT"
    assert artifact["shutdown_reason"] == "OPERATOR_INTERRUPT"
    assert artifact["interruption_type"] == "KeyboardInterrupt"
    assert artifact["pre_shutdown_health"] == {
        "phase": "AWAITING_OPERATOR_ACTIVATION", "reason": None,
        "adapter_status": "LIVE_TAIL", "activation_allowance_started": True,
        "order_submit_reachable": False,
    }
    assert artifact["final_shutdown_health"] == {
        "phase": "FAILED", "reason": "STARTUP_SHUTDOWN", "adapter_status": "REVOKED",
    }
    assert artifact["final_shutdown_health_reason"] == "STARTUP_SHUTDOWN"

    expected_sources = {
        "backend/backtesting/certified_native_paper_bridge_v1.py":
            "769d52ee42cda48875b6c1ff19489dbe7f81de799a12a9605590806981963158",
        "backend/market_data/current_candle_authority_v1.py":
            "bcfe63f74c7d22880ed9d04288279743f92698273157d5944a7817db0c7f5561",
    }
    assert artifact["source_sha256"] == expected_sources
    for path, digest in expected_sources.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest

    assert artifact["native_market_evidence"]["prefix_bytes"] == 30082
    assert artifact["native_market_evidence"]["prefix_sha256"] == (
        "68d18498dd496f2f222d2f7afc320065ca7e005824fdde207324ee6c58618c9d"
    )
    assert artifact["native_market_evidence"]["full_file_was_growing"] is True
    assert artifact["native_timing_evidence"]["prefix_bytes"] == 18528
    assert artifact["native_timing_evidence"]["prefix_sha256"] == (
        "88aac13ee30060b11d472304161918dd7cbbbaafc2dd74bc3356d0dd1baace0c"
    )
    for value in artifact["stable_evidence"].values():
        assert value["path"].startswith(".arms-dev/")
        assert len(value["sha256"]) == 64
        assert all(char in "0123456789abcdef" for char in value["sha256"])


def test_direct_dependency_inventory_cannot_silently_omit_a_clock_call():
    import ast
    manifest=json.loads(Path("backend/tests/clock_preflight_sprint15t.json").read_text())
    expected={(row["path"],c["line"],c["call"]) for row in manifest["direct_clock_dependencies"]
              if row["path"].endswith(".py") for c in row["calls"]}
    actual=set()
    for path in Path("backend").rglob("*.py"):
        if "tests" in path.parts:continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            if isinstance(node,ast.Call):
                name=ast.unparse(node.func)
                if name in ("datetime.now","datetime.utcnow","time.time","time.monotonic","time.perf_counter","clock") or name.endswith((".clock","._clock")):
                    actual.add((path.as_posix(),node.lineno,name))
    assert actual==expected


def test_offline_model_is_not_imported_by_runtime():
    for root in (Path("backend"),Path("integrations")):
        for path in root.rglob("*.py"):
            if "tests" not in path.parts:
                assert "clock_preflight_v1" not in path.read_text(encoding="utf-8-sig")


@pytest.mark.parametrize("value",[None,True,1,1.5,"", "  "])
def test_review_provenance_requires_explicit_text_identity(value):
    x=fixture_inputs();x["bounds"]=replace(x["bounds"],provenance=value)
    result=assess(**x)
    assert result["status"]=="UNKNOWN" and not any(result["clock_ready"].values())
