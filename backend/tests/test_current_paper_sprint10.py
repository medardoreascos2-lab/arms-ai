"""Explicit synthetic current feed: no network, market dataset or real orders."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, timedelta, timezone
import sqlite3
import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.api.current_paper_app_v1 import create_current_paper_app_v1
from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.backtesting.paper_runtime_v1 import PaperRuntimeV1
from backend.models.candle import Candle
from backend.config.api_settings import APISettings
from backend.market_data.current_candle_authority_v1 import (
    CurrentCandleAuthorityV1, CurrentFeedContractV1, CurrentMarketEventV1,
    _certify_native_same_callback_closed)
from backend.services.certified_market_calendar_v2 import CertifiedCalendarSnapshotV2
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.special_hours_snapshot_v2 import CertifiedSpecialHoursSnapshotV2, CertifiedSpecialHoursWindowV2
from backend.tests.test_paper_research_sprint07r import config
from backend.tests.test_paper_runtime_sprint08 import witness, fill_count
from backend.tests.test_production_certified_outcome_v17 import api_settings

UTC = timezone.utc
START = datetime(2026, 9, 14, 14, tzinfo=UTC)


def gate(start=START, label="OPEN", zone="UTC"):
    clock = [start+timedelta(minutes=1)]
    days = frozenset(start.date()+timedelta(days=n) for n in range(-3, 10))
    hours = CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=CertifiedCalendarSnapshotV2(days, frozenset()))
    contract = CurrentFeedContractV1("SYNTHETIC_FIXTURE", "NQ DEC26 FIXTURE", zone, label,
        "EXPLICIT_TEST_CALENDAR", start-timedelta(days=3), start+timedelta(days=10), fixture=True)
    return CurrentCandleAuthorityV1(contract=contract, market_hours=hours, maximum_age_seconds=30,
                                  clock=lambda: clock[0]), clock


def event(index, start=START, **changes):
    opened = start+timedelta(minutes=index)
    return replace(CurrentMarketEventV1("SYNTHETIC_FIXTURE", "NQ", "NQ DEC26 FIXTURE",
        "CLOSED_CANONICAL_CANDLE", opened+timedelta(minutes=1), opened+timedelta(minutes=1),
        opened, index, str(index), 10000, 10000, 10000, 10000, 10), **changes)


REAL_CLOSE = datetime(2026, 10, 1, 7, 52, tzinfo=UTC)
REAL_EARLY = datetime.fromisoformat("2026-10-01T07:51:59.9997804+00:00")


def _boundary_case(*, emitted=REAL_EARLY, received=None, close=REAL_CLOSE,
                   sequence=0, event_id="native:67", **changes):
    received = received or close + timedelta(milliseconds=10)
    return event(0, close-timedelta(minutes=1), bar_time=close,
                 event_time=emitted, received_at=received, sequence=sequence,
                 event_id=event_id, open=30853.25, high=30877.5,
                 low=30851.25, close=30865.25, volume=626, **changes)


def _boundary_gate(close=REAL_CLOSE):
    g, clock = gate(close-timedelta(minutes=2), label="CLOSE")
    clock[0] = close + timedelta(milliseconds=11)
    g.connection(True)
    return g, clock


@pytest.mark.parametrize("offset_ms", [0, 203])
def test_closed_at_or_after_boundary_needs_no_native_proof(offset_ms):
    g, clock = _boundary_gate()
    clock[0] = REAL_CLOSE + timedelta(milliseconds=offset_ms+10)
    e = _boundary_case(emitted=REAL_CLOSE+timedelta(milliseconds=offset_ms),
                       received=clock[0])
    row = g.admit(e)
    assert e.closed_boundary_proof is None
    assert row.event_time == e.event_time
    assert row.available_at == REAL_CLOSE


def test_real_preboundary_close_requires_native_proof_and_preserves_source_time():
    g, _ = _boundary_gate()
    with pytest.raises(ValueError, match="STALE_DATA"):
        g.admit(_boundary_case())
    assert g.closed_count == 0

    g, _ = _boundary_gate()
    source = _boundary_case()
    certified = _certify_native_same_callback_closed(source)
    row = g.admit(certified)
    assert source.closed_boundary_proof is None
    assert certified.event_time == row.event_time == REAL_EARLY
    assert row.received_at > row.available_at == REAL_CLOSE
    assert g.maximum_age == 30
    assert g.closed_count == 1


def test_genuinely_early_unproven_close_is_rejected():
    g, _ = _boundary_gate()
    with pytest.raises(ValueError, match="STALE_DATA"):
        g.admit(_boundary_case(emitted=REAL_CLOSE-timedelta(seconds=1)))
    assert g.closed_count == 0


def test_certified_receipt_at_exact_close_boundary_is_admitted():
    g, _ = _boundary_gate()
    event_at_boundary = _certify_native_same_callback_closed(
        _boundary_case(received=REAL_CLOSE))
    assert g.admit(event_at_boundary).received_at == REAL_CLOSE


@pytest.mark.parametrize("case,reason", [
    ("receipt_before", "STALE_DATA"),
    ("forming", "INVALID_CLOSED_PROVENANCE"),
    ("raw", "INVALID_CLOSED_PROVENANCE"),
    ("forged", "INVALID_CLOSED_PROVENANCE"),
    ("stale_source", "TIME_SYNC_INVALID"),
    ("stale_receipt", "TIME_SYNC_INVALID"),
    ("future", "TIME_SYNC_INVALID"),
    ("invalid_ohlcv", "INVALID_CANDLE"),
    ("contract_window", "UNKNOWN_CONTRACT"),
    ("market_closed", "MARKET_HOURS_UNCERTIFIED_OR_CLOSED"),
])
def test_native_closed_proof_never_bypasses_other_gates(case, reason):
    close = (datetime(2026, 10, 4, 15, tzinfo=UTC)
             if case == "market_closed" else REAL_CLOSE)
    g, clock = _boundary_gate(close)
    e = _certify_native_same_callback_closed(_boundary_case(
        close=close, emitted=close-timedelta(microseconds=220)))
    if case == "receipt_before":
        e = replace(e, received_at=close-timedelta(microseconds=100))
    elif case in ("forming", "raw"):
        e = replace(e, kind="FORMING_CANDLE" if case == "forming" else "RAW_EVENT")
    elif case == "forged":
        e = replace(e, closed_boundary_proof="CERTIFIED_NATIVE_SAME_CALLBACK_CLOSED")
    elif case == "stale_source":
        e = replace(e, event_time=close-timedelta(seconds=31))
    elif case == "stale_receipt":
        e = replace(e, received_at=close+timedelta(seconds=1))
        clock[0] = close+timedelta(seconds=32)
    elif case == "future":
        e = replace(e, event_time=close+timedelta(seconds=1))
    elif case == "invalid_ohlcv":
        e = replace(e, low=e.high+0.25)
    elif case == "contract_window":
        g = CurrentCandleAuthorityV1(
            contract=replace(g.contract, valid_until=close-timedelta(microseconds=1)),
            market_hours=g.market_hours, maximum_age_seconds=30, clock=lambda: clock[0])
        g.connection(True)
    with pytest.raises(ValueError, match=reason):
        g.admit(e)
    assert g.closed_count == 0
    assert "RECOVERY_REQUIRED" in g.reasons()


@pytest.mark.parametrize("repeat", range(5))
def test_real_seq53_then_seq67_requires_proof_and_preserves_continuity(repeat):
    first_close = REAL_CLOSE-timedelta(minutes=1)
    first = _boundary_case(close=first_close,
        emitted=datetime.fromisoformat("2026-10-01T07:51:00.2030694+00:00"),
        received=first_close+timedelta(milliseconds=210),
        sequence=0, event_id="native:53")
    second = _certify_native_same_callback_closed(_boundary_case(sequence=1))
    g, clock = _boundary_gate(first_close)
    clock[0] = first.received_at
    assert g.admit(first).event_id == "native:53"
    clock[0] = second.received_at+timedelta(milliseconds=1)
    assert g.admit(second).event_id == "native:67"
    assert g.closed_count == 2 and g.last_closed == REAL_CLOSE
    assert g.admit(replace(second, received_at=second.received_at+timedelta(milliseconds=1))) is None
    assert g.duplicate_count == 1


@pytest.mark.parametrize("case,reason", [
    ("sequence_gap", "OUT_OF_ORDER"),
    ("duplicate_conflict", "DUPLICATE_CONFLICT"),
])
def test_native_closed_proof_keeps_order_and_duplicate_rules(case, reason):
    g, clock = _boundary_gate()
    first = _certify_native_same_callback_closed(_boundary_case())
    assert g.admit(first) is not None
    clock[0] += timedelta(minutes=1)
    next_close = REAL_CLOSE+timedelta(minutes=1)
    second = _certify_native_same_callback_closed(_boundary_case(
        close=next_close, emitted=next_close-timedelta(microseconds=220),
        sequence=2 if case == "sequence_gap" else 1,
        event_id="native:68" if case == "sequence_gap" else first.event_id))
    with pytest.raises(ValueError, match=reason):
        g.admit(second)
    assert g.closed_count == 1


def service(tmp_path, start=START):
    g, clock = gate(start)
    class ExistingFlowEntryEvidence:
        """Explicit deterministic test evidence for legacy accounting cases."""
        def observe(self, row):
            assert row.calendar_sha256 == g.digest

        def inspect(self, **kwargs):
            return []

    s = CurrentPaperServiceV1(gate=g, config=config(), settings=APISettings(),
        state_path=tmp_path/"current.sqlite", initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT",
        entry_authority=ExistingFlowEntryEvidence())
    s.connection(True)
    original_ingest = s.ingest

    def ingest_with_test_worker_health(e):
        # The real lifecycle polls every 0.25s; represent that separate worker
        # heartbeat at the deterministic synthetic event's clock boundary.
        if s.gate.connected and not s.gate.fault:
            s._health_at = g.clock()
            s._health_live = True
        result = original_ingest(e)
        if s.gate.connected and not s.gate.fault:
            s.publish_health(coordinator={"status": "LIVE", "source_adapter_status": "LIVE_TAIL",
                "bridge": {"status": "LIVE"}}, worker_alive=True)
        return result

    s.ingest = ingest_with_test_worker_health
    return s, clock


def deliver(s, clock, e):
    clock[0] = e.received_at
    return s.ingest(e)


def test_authenticated_enable_is_health_bound_and_disconnect_requires_reenable(api_settings,tmp_path):
    s,clock=service(tmp_path)
    app=create_current_paper_app_v1(service=s,admin_token="test-only-token",
        dashboard_origin="http://127.0.0.1:3000")
    headers={"X-ARMS-ADMIN-TOKEN":"test-only-token",
        "X-ARMS-REQUEST-ID":"request-1","X-ARMS-REQUEST-NONCE":"nonce-1"}
    with TestClient(app) as client:
        assert client.post("/api/v2/paper/enable").status_code == 401
        assert client.post("/api/v2/paper/enable",headers={"X-ARMS-ADMIN-TOKEN":"wrong"}).status_code == 401
        assert client.post("/api/v2/paper/enable",headers=headers).status_code == 409
        deliver(s,clock,event(0))
        assert client.post("/api/v2/paper/enable",headers=headers).status_code == 200
        assert s._runtime._enabled is True
        s.connection(False)
        assert s._runtime._enabled is False
        s.connection(True)
        deliver(s,clock,event(1,sequence=1,event_id="1"))
        assert s._runtime._enabled is False
        response=client.post("/api/v2/paper/enable",headers=headers)
        assert response.status_code == 409
        assert response.json()['detail']=='FRESH_AUTHORIZATION_SESSION_REQUIRED'
        assert s._runtime._enabled is False
        audit=s._runtime.get_authority_audit()
        assert audit['status']=='COMMITTED_EVIDENCE' and audit['total']==2
        disabled,enabled=audit['records']
        assert disabled['previous_state']=='ENABLED'
        assert disabled['new_state']=='DISABLED_RUNTIME_FAILURE'
        assert disabled['reason']=='PROVIDER_DISCONNECTED'
        assert disabled['initiating_path']=='CURRENT_PAPER_CONNECTION'
        assert enabled['previous_state']=='DISABLED'
        assert enabled['new_state']=='ENABLED'
        assert enabled['request_id']=='request-1'
        assert enabled['request_nonce']=='nonce-1'
        assert enabled['readiness_snapshot']['live_execution_allowed'] is False


def test_forming_raw_duplicate_and_complete_htf_equivalence():
    g, clock = gate()
    g.connection(True)
    for seq, kind in enumerate(("RAW_EVENT", "FORMING_CANDLE")):
        assert g.admit(event(0, sequence=seq, event_id=str(seq), kind=kind)) is None
    assert g.closed_count == 0
    current, historical = ClosedBarAggregatorV1(history_limit=50), ClosedBarAggregatorV1(history_limit=50)
    for i in range(120):
        e = event(i, sequence=i+2, event_id=str(i+2))
        clock[0] = e.received_at
        row = g.admit(e)
        assert row.available_at <= clock[0]
        current.update_completed(row.candle())
        historical.update_completed(Candle("NQ", "1m", e.open, e.high, e.low, e.close, e.volume,
                                           e.bar_time))
        assert g.admit(replace(e, received_at=e.received_at+timedelta(seconds=1))) is None
        assert current.history("15m") == historical.history("15m")
        assert current.history("1h") == historical.history("1h")
        assert all(x.timestamp < row.available_at for x in current.history("1h"))
    assert current.emitted_counts == {"15m":8, "1h":2}
    assert g.closed_count == g.duplicate_count == 120


@pytest.mark.parametrize("changes,reason", [
    ({"low":10001}, "INVALID_CANDLE"), ({"open":10000.1}, "INVALID_CANDLE"),
    ({"volume":-1}, "INVALID_CANDLE"), ({"volume":1.5}, "INVALID_CANDLE"),
    ({"contract":"OTHER"}, "UNKNOWN_CONTRACT"),
    ({"bar_time":START.replace(tzinfo=None)}, "TIME_SYNC_INVALID"),
    ({"bar_time":START+timedelta(minutes=1)}, "TIME_SYNC_INVALID"),
    ({"quality_flags":("BAD",)}, "INVALID_CANDLE"),
    ({"event_time":START+timedelta(minutes=2)}, "TIME_SYNC_INVALID"),
])
def test_invalid_gate_is_latched(changes, reason):
    g, _ = gate()
    g.connection(True)
    with pytest.raises(ValueError, match=reason): g.admit(event(0, **changes))
    assert g.closed_count == 0 and "RECOVERY_REQUIRED" in g.reasons()
    with pytest.raises(RuntimeError): g.admit(event(0))


@pytest.mark.parametrize("start", [datetime(2026,3,9,14,tzinfo=UTC), datetime(2026,11,2,14,tzinfo=UTC)])
def test_explicit_end_labels_and_dst_offsets(start):
    g, _ = gate(start, label="CLOSE")
    g.connection(True)
    row = g.admit(event(0, start, bar_time=start+timedelta(minutes=1)))
    assert row.canonical_timestamp.astimezone(UTC) == start
    assert row.canonical_timestamp.utcoffset().total_seconds() == (-18000 if start.month == 3 else -21600)


@pytest.mark.parametrize("case", ["gap", "order", "late", "conflict"])
def test_continuity_failure(case):
    g, clock = gate()
    g.connection(True)
    g.admit(event(0))
    e = event(1)
    if case == "gap": e = event(2, sequence=1, event_id="1")
    if case == "order": e = replace(e, sequence=4)
    if case == "late": e = event(0, sequence=1, event_id="1")
    if case == "conflict": e = event(0, high=10001)
    clock[0] = e.received_at
    with pytest.raises(ValueError): g.admit(e)
    assert g.closed_count == 1 and "RECOVERY_REQUIRED" in g.reasons()


def test_account_execution_journal_reads_and_recovery(api_settings, tmp_path, monkeypatch):
    s, clock = service(tmp_path)
    assert s.get_snapshot()["account_overview"] is None
    deliver(s, clock, event(0))
    r = s._runtime
    witness(r)
    s.control("enable")
    for i in range(1,8):
        e = event(i, high=10060 if i == 5 else 10000)
        snap = deliver(s, clock, e)
        account = snap["account_overview"]
        assert s.ingest(e)["account_overview"] == account
    assert fill_count(r) == snap["completed_trades"] == snap["journal_completed"] == 1
    assert account["realized_pnl"] == 1170
    assert account["balance"] == account["equity"] == 151170
    assert snap["execution_kind"] == "SIMULATED / PAPER"
    with sqlite3.connect(tmp_path/"current.sqlite") as db:
        assert db.execute("SELECT count(*) FROM journal").fetchone()[0] == 1
        journal = json.loads(db.execute("SELECT payload FROM journal").fetchone()[0])
        assert journal["execution_kind"] == snap["latest_canonical_trade"]["execution_kind"] == "SIMULATED / PAPER"
        assert journal["net_pnl"] == 1170
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 8
    app = create_current_paper_app_v1(service=s, admin_token="fixture-token")
    with TestClient(app) as client:
        assert client.post("/api/v2/paper/enable").status_code == 401
        assert client.post("/api/v2/paper/step",headers={"X-ARMS-ADMIN-TOKEN":"fixture-token"}).status_code == 409
        for owner, method in ((s,"ingest"),(r._paper.runtime.lifecycle,"submit_signal"),
                              (r._paper.runtime.lifecycle,"update_position")):
            monkeypatch.setattr(owner, method, Mock(side_effect=AssertionError("read side effect")))
        for _ in range(3):
            assert client.get("/api/v2/backtesting/dashboard").json()["paper_research"]["account_overview"] == account
        clock[0] += timedelta(seconds=31)
        assert client.get("/api/v2/paper/readiness").json()["paper_ready"] is False
        assert "STALE_DATA" in s.get_snapshot()["readiness_reasons"]
    recovered, _ = service(tmp_path)
    assert recovered._runtime._paper is None
    assert recovered.get_snapshot()["recovery_required"]
    assert recovered.get_snapshot()["account_overview"] == account
    with pytest.raises(RuntimeError): recovered.control("enable")


@pytest.mark.parametrize("veto", ["risk", "rejected", "disable", "hold", "emergency_block"])
def test_zero_execution_under_veto(api_settings, tmp_path, veto):
    s, clock = service(tmp_path)
    deliver(s, clock, event(0))
    r = s._runtime
    witness(r, entries=() if veto == "hold" else (5,))
    s.control("enable")
    if veto in {"disable", "emergency_block"}: s.control(veto)
    accounting = r._paper.runtime
    if veto == "risk":
        saved = accounting.account.capture_state()
        saved["state"].update(trading_blocked=True, blocking_reasons=["fixture"])
        accounting.account.restore_state(snapshot=saved)
    if veto == "rejected":
        accounting.lifecycle.execution_risk_gate_v1.evaluate_trade = Mock(return_value={"execution":"BLOCKED"})
    for i in range(1,8): deliver(s, clock, event(i))
    assert fill_count(r) == 0
    assert not accounting.journal.trades and not accounting.completed
    assert accounting.account.get_state()["realized_pnl"] == 0
    s.shutdown()


def test_disconnect_valid_reconnect_preserves_position_management(api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s, clock, event(0))
    witness(s._runtime)
    s.control("enable")
    for i in range(1,5): deliver(s, clock, event(i))
    before = s.get_snapshot()["account_overview"]
    s.connection(False)
    assert not s.get_snapshot()["paper_ready"]
    with pytest.raises(RuntimeError): s.ingest(event(5))
    assert s.get_snapshot()["account_overview"] == before
    s.connection(True)
    assert "CONTINUITY_PENDING" in s.get_snapshot()["readiness_reasons"]
    s.control("disable")
    snap = deliver(s, clock, event(5, low=9970))
    assert snap["completed_trades"] == 1 and snap["account_overview"]["realized_pnl"] == -630
    assert fill_count(s._runtime) == 1
    s.shutdown()


def test_multiday_stream_soak_with_bounded_context(api_settings, tmp_path):
    start = datetime(2026,9,14,20,50,tzinfo=UTC)  # Ten minutes to daily maintenance.
    s, clock = service(tmp_path, start)
    timestamps = []
    t = start
    while len(timestamps) < 3000:
        if s.gate._open(t) and s.gate._open(t+timedelta(seconds=59)):
            timestamps.append(t)
        t += timedelta(minutes=1)
    for i, t in enumerate(timestamps):
        price = 10000 if i < 6 else 10010
        e = event(0, t, sequence=i, event_id=str(i), open=price, close=price,
                  high=10060 if i == 5 else price, low=9980 if i == 7 else price)
        if i and i % 500 == 0:
            clock[0] += timedelta(seconds=31)
            assert "STALE_DATA" in s.get_snapshot()["readiness_reasons"]
            s.connection(False)
            s.connection(True)
        snap = deliver(s, clock, e)
        if i == 0:
            witness(s._runtime, entries=(5,7))
            s.control("enable")
        if i % 13 == 0:
            before = snap["account_overview"]
            assert s.ingest(e)["account_overview"] == before
    r = s._runtime._paper.runtime
    snap = s.get_snapshot()
    assert snap["completed_trades"] == snap["journal_completed"] == fill_count(s._runtime) == 2
    assert [x["net_pnl"] for x in r.completed] == [1170,-630]
    assert snap["account_overview"]["balance"] == snap["account_overview"]["equity"] == 150540
    assert snap["account_overview"]["realized_pnl"] == sum(x.pnl for x in r.journal.trades) == 540
    assert len({x["position_id"] for x in r.completed}) == 2
    assert len(r.rows) == len(s._runtime._rows) == 1
    assert len(r.session.candle_history) <= 50 and len(s.gate._seen) <= 2048
    assert all(len(s._runtime._htf.history(tf)) <= 50 for tf in ("15m","1h"))
    assert not r.states and not r.risk_evaluations
    assert snap["market_data"]["closed_candles"] == 3000
    assert snap["htf_emitted"]["1h"] > 40
    s.shutdown()


def test_real_detector_historical_current_context_parity(api_settings, tmp_path):
    g, clock = gate()
    g.connection(True)
    rows = []
    for i in range(121):
        e = event(i)
        clock[0] = e.received_at
        rows.append(g.admit(e))
    historical = PaperRuntimeV1(mode="PAPER_RESEARCH", config=config(), settings=APISettings(),
        policy=g, observations=rows, contract=g.contract.contract, state_path=tmp_path/"historical.sqlite",
        initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
    current, now = service(tmp_path)
    for i in range(120):
        h = historical.step()
        c = deliver(current, now, event(i))
        assert c["strategy_evidence"] == h["strategy_evidence"]
        assert c["latest_decision"] == h["latest_decision"]
        assert c["timeframe_readiness"] == h["timeframe_readiness"]
        assert c["account_overview"] == h["account_overview"]
    current.shutdown()
    historical.shutdown()


def test_special_hours_contract_digest_is_stable_and_closure_is_enforced():
    g, clock = gate()
    special = CertifiedSpecialHoursSnapshotV2((CertifiedSpecialHoursWindowV2(START.date(), time(8), time(9)),))
    provider = CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=g.market_hours.calendar_snapshot,
                                                   special_hours_snapshot=special)
    make = lambda: CurrentCandleAuthorityV1(contract=g.contract, market_hours=provider,
                                           maximum_age_seconds=30, clock=lambda:clock[0])
    a, b = make(), make()
    assert a.digest == b.digest and a.digest != g.digest
    a.connection(True)
    with pytest.raises(ValueError,match="MARKET_HOURS"): a.admit(event(0))  # 09:00 Chicago closed.


def test_uncovered_calendar_and_reconnect_gap_never_mutate_account(api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s,clock,event(0))
    s.control("enable")
    before = s.get_snapshot()["account_overview"]
    s.connection(False)
    s.connection(True)
    with pytest.raises(ValueError,match="RECOVERY_REQUIRED"):
        deliver(s,clock,event(2,sequence=1,event_id="1"))
    assert s.get_snapshot()["recovery_required"]
    assert s.get_snapshot()["account_overview"] == before
    assert fill_count(s._runtime) == 0
    s.shutdown()
    g, clock = gate()
    g.market_hours = CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=CertifiedCalendarSnapshotV2(frozenset(),frozenset()))
    g.connection(True)
    with pytest.raises(ValueError,match="MARKET_HOURS"): g.admit(event(0))


def test_parallel_duplicate_delivery_and_forming_prices_cannot_fill(api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s,clock,event(0))
    witness(s._runtime)
    s.control("enable")
    for i in range(1,5): deliver(s,clock,event(i))
    before = s.get_snapshot()["account_overview"]
    forming = event(5,kind="FORMING_CANDLE",high=10100,low=9900)
    deliver(s,clock,forming)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(s.ingest,[forming]*12))
    assert s.get_snapshot()["account_overview"] == before
    assert not s._runtime._paper.runtime.completed
    close = event(5,sequence=6,event_id="6",high=10060)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(s.ingest,[close]*12))
    assert fill_count(s._runtime) == s.get_snapshot()["completed_trades"] == 1
    assert s.get_snapshot()["market_data"]["closed_candles"] == 6
    s.shutdown()


@pytest.mark.parametrize("age", [0,-1,float("nan"),float("inf"),True])
def test_invalid_freshness_bound_rejected(age):
    g,_ = gate()
    with pytest.raises(ValueError):
        CurrentCandleAuthorityV1(contract=g.contract,market_hours=g.market_hours,
                                 maximum_age_seconds=age,clock=g.clock)


def test_bad_clock_projection_blocks_without_mutation(api_settings,tmp_path):
    s,clock = service(tmp_path)
    deliver(s,clock,event(0))
    s.control("enable")
    before = s.get_snapshot()["account_overview"]
    clock[0] = START.replace(tzinfo=None)
    snap = s.get_snapshot()
    assert not snap["paper_ready"] and "TIME_SYNC_INVALID" in snap["readiness_reasons"]
    assert snap["market_data"]["data_age_seconds"] is None
    assert snap["account_overview"] == before
    s.shutdown()


@pytest.mark.parametrize("friday,sunday,offsets", [
    (datetime(2026,3,6,21,59,tzinfo=UTC), datetime(2026,3,8,22,tzinfo=UTC), (-21600,-18000)),
    (datetime(2026,10,30,20,59,tzinfo=UTC), datetime(2026,11,1,23,tzinfo=UTC), (-18000,-21600)),
])
def test_reconnect_across_actual_dst_weekend_preserves_gap(friday,sunday,offsets):
    g,clock = gate(friday)
    g.connection(True)
    first = g.admit(event(0,friday))
    g.connection(False)
    g.connection(True)
    reopened = event(0,sunday,sequence=1,event_id="1")
    clock[0] = reopened.received_at
    last = g.admit(reopened)
    assert (first.canonical_timestamp.utcoffset().total_seconds(),
            last.canonical_timestamp.utcoffset().total_seconds()) == offsets
    assert last.canonical_timestamp.astimezone(UTC) == sunday
    assert g.closed_count == 2 and not g.reasons()
    htf = ClosedBarAggregatorV1(history_limit=50)
    htf.update_completed(first.candle())
    htf.update_completed(last.candle())
    assert htf.emitted_counts == {"15m":0,"1h":0}


def test_paper_execution_enabled_snapshot_tracks_canonical_authority(
        api_settings, tmp_path):
    s, clock = service(tmp_path)

    # No runtime exists yet: fail closed must be explicit, not None/missing.
    assert s.get_snapshot()["paper_execution_enabled"] is False

    deliver(s, clock, event(0))
    assert s.get_snapshot()["paper_execution_enabled"] is False

    witness(s._runtime)
    s.control("enable")
    assert s.get_snapshot()["paper_execution_enabled"] is True

    s.control("disable")
    assert s.get_snapshot()["paper_execution_enabled"] is False

    s.shutdown()


def test_runtime_health_loss_revokes_paper_authority_fail_closed(
        api_settings, tmp_path):
    s, clock = service(tmp_path)
    deliver(s, clock, event(0))
    witness(s._runtime)
    s.control("enable")
    assert s.get_snapshot()["paper_execution_enabled"] is True

    s.invalidate_health(reason="RUNTIME_HEALTH_LOSS",
                        initiating_path="TEST_HEALTH_MONITOR")
    snapshot = s.get_snapshot()
    assert snapshot["paper_execution_enabled"] is False
    assert snapshot["paper_ready"] is False
    assert snapshot["live_execution_allowed"] is False
    assert snapshot["external_order_authority"] is False
    assert snapshot["broker_live_order_authority"] is False
    assert snapshot["ninjatrader_control_authority"] is False
    assert "CURRENT_PAPER_HEALTH_UNAVAILABLE" in snapshot["readiness_reasons"]
    s.shutdown()
