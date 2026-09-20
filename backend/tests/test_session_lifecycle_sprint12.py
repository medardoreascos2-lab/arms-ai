"""Synthetic lifecycle witnesses; dates/hours are NOT native calendar evidence."""
from dataclasses import replace
from datetime import datetime, timedelta, time, timezone

import pytest

from backend.market_data.session_state_v1 import SessionStateAuthorityV1, SessionStateV1, readiness_matrix
from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
from backend.services.certified_market_calendar_v2 import CertifiedCalendarSnapshotV2
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.special_hours_snapshot_v2 import CertifiedSpecialHoursSnapshotV2, CertifiedSpecialHoursWindowV2
from backend.tests.test_current_paper_sprint10 import gate, event, service, deliver, api_settings
from backend.tests.test_paper_runtime_sprint08 import witness, fill_count

UTC = timezone.utc


def stamp(s):
    return datetime.fromisoformat(s).astimezone(UTC)


@pytest.mark.parametrize("when,expected", [
    ("2026-09-14T15:59:00-05:00", "REOPENING"),
    ("2026-09-14T16:00:00-05:00", "DAILY_MAINTENANCE"),
    ("2026-09-14T17:00:00-05:00", "REOPENING"),
    ("2026-09-18T16:00:00-05:00", "WEEKEND_CLOSED"),
    ("2026-09-19T12:00:00-05:00", "WEEKEND_CLOSED"),
    ("2026-09-20T16:59:00-05:00", "WEEKEND_CLOSED"),
    ("2026-09-20T17:00:00-05:00", "REOPENING"),
])
def test_explicit_state_independent_of_provider(when, expected):
    g, _ = gate()
    authority = SessionStateAuthorityV1(g.market_hours)
    assert authority.resolve(stamp(when)).state == expected
    before = vars(g).copy()
    for provider in ("CONNECTED", "DISCONNECTED", "CONNECTING", "UNKNOWN"):
        matrix = readiness_matrix(authority.resolve(stamp(when)), provider, fresh=False, recovery_clear=True)
        assert not matrix["new_entry_admission"] and not matrix["strategy_admission"]
        assert matrix["external_order_authority"] is False
    assert vars(g) == before


@pytest.mark.parametrize("state", ["PRE_OPEN", "OPEN", "DAILY_MAINTENANCE", "SCHEDULED_CLOSED", "WEEKEND_CLOSED", "HOLIDAY_CLOSED", "EARLY_CLOSE", "REOPENING", "UNKNOWN"])
@pytest.mark.parametrize("provider", ["CONNECTED", "DISCONNECTED", "CONNECTING", "UNKNOWN"])
def test_full_matrix(state, provider):
    s = SessionStateV1(state, state in {"OPEN", "REOPENING"})
    result = readiness_matrix(s, provider, fresh=True, recovery_clear=True, risk_ready=True, enabled=True)
    assert result["new_entry_admission"] == (state == "OPEN" and provider == "CONNECTED")
    assert result["external_order_authority"] is False
    assert not readiness_matrix(s, provider, fresh=True, recovery_clear=False, risk_ready=True, enabled=True)["new_entry_admission"]


@pytest.mark.parametrize("before,after", [
    ("2026-09-14T15:59:00-05:00", "2026-09-14T17:00:00-05:00"),
    ("2026-09-18T15:59:00-05:00", "2026-09-20T17:00:00-05:00"),
    ("2026-03-06T15:59:00-06:00", "2026-03-08T17:00:00-05:00"),
    ("2026-10-30T15:59:00-05:00", "2026-11-01T17:00:00-06:00"),
])
def test_gap_reopen_htf_requires_every_real_minute(before, after):
    start, reopen = stamp(before), stamp(after)
    g, clock = gate(start)
    g.connection(True)
    first = g.admit(event(0, start))
    htf = ClosedBarAggregatorV1()
    htf.update_completed(first.candle())
    clock[0] = reopen
    assert "STALE_DATA" in g.reasons()
    state = SessionStateAuthorityV1(g.market_hours).resolve(reopen, last_closed=g.last_closed)
    assert state.state == "REOPENING"
    for i in range(60):
        e = event(i, reopen, sequence=i+1, event_id=str(i+1))
        clock[0] = e.received_at
        row = g.admit(e)
        assert row.canonical_timestamp.astimezone(UTC) == reopen + timedelta(minutes=i)
        htf.update_completed(row.candle())
        assert htf.emitted_counts == {"15m":(i+1)//15, "1h":(i+1)//60}
        assert htf.available_at <= clock[0]
        assert g.admit(e) is None
    assert g.closed_count == 61 and g.duplicate_count == 60
    assert SessionStateAuthorityV1(g.market_hours).resolve(clock[0], last_closed=g.last_closed).state == "OPEN"


def special_gate(start, closed=(), window=None):
    g, clock = gate(start)
    calendar = replace(g.market_hours.calendar_snapshot, closed_dates=frozenset(closed))
    g.market_hours = CertifiedMarketHoursRuntimeProviderV2(calendar_snapshot=calendar,
        special_hours_snapshot=CertifiedSpecialHoursSnapshotV2((window,)) if window else None)
    g.connection(True)
    return g, clock


def test_explicit_fixture_holiday_early_close_preopen_and_unknown():
    start = stamp("2026-09-14T08:00:00-05:00")
    day = start.date()
    g, _ = special_gate(start, window=CertifiedSpecialHoursWindowV2(day,time(8),time(12)))
    a = SessionStateAuthorityV1(g.market_hours)
    assert a.resolve(stamp("2026-09-14T07:00:00-05:00")).state == "PRE_OPEN"
    assert a.resolve(stamp("2026-09-14T12:00:00-05:00")).state == "EARLY_CLOSE"
    g, _ = special_gate(start, closed=(day,))
    assert SessionStateAuthorityV1(g.market_hours).resolve(start).state == "HOLIDAY_CLOSED"
    unknown = SessionStateAuthorityV1(CertifiedMarketHoursRuntimeProviderV2())
    assert unknown.resolve(start).state == "UNKNOWN"
    assert a.resolve(start.replace(tzinfo=None)).state == "UNKNOWN"


@pytest.mark.parametrize("attack", ["old_close", "out_of_order", "old_raw_after_close", "old_forming_after_close", "missing_open_minute"])
def test_late_boundary_events_never_create_second_close(attack):
    start = stamp("2026-09-14T15:59:00-05:00")
    reopen = stamp("2026-09-14T17:00:00-05:00")
    g, clock = gate(start)
    g.connection(True)
    original = event(0,start)
    g.admit(original)
    clock[0] = reopen + timedelta(minutes=1)
    e = event(0,reopen,sequence=1,event_id="1")
    if attack == "old_close": e = replace(e,bar_time=start)
    if attack == "out_of_order": e = replace(e,sequence=0,event_id="different")
    if attack == "missing_open_minute":
        e = event(1,reopen,sequence=1,event_id="1")
        clock[0] = e.received_at
    if "after_close" in attack:
        clock[0] = start+timedelta(minutes=1,seconds=1)
        e = replace(e, event_time=clock[0], received_at=clock[0], bar_time=start,
                    kind="RAW_EVENT" if "raw" in attack else "FORMING_CANDLE")
    with pytest.raises(ValueError): g.admit(e)
    assert g.closed_count == 1 and g.fault


def test_holiday_gap_has_no_synthetic_bucket():
    start = stamp("2026-09-14T15:59:00-05:00")
    reopen = stamp("2026-09-16T00:00:00-05:00")
    g, clock = special_gate(start, closed=((start+timedelta(days=1)).date(),),
        window=CertifiedSpecialHoursWindowV2(start.date(),time(0),time(16)))
    htf = ClosedBarAggregatorV1()
    htf.update_completed(g.admit(event(0,start)).candle())
    for i in range(60):
        e = event(i,reopen,sequence=i+1,event_id=str(i+1))
        clock[0] = e.received_at
        htf.update_completed(g.admit(e).candle())
    assert g.closed_count == 61
    assert htf.emitted_counts == {"15m":4,"1h":1}


def test_recorded_template_early_close_keeps_partial_hour_unemitted():
    import json
    from pathlib import Path
    from datetime import date
    evidence=json.loads(Path(__file__).with_name("session_source_evidence_sprint12.json").read_text())
    row=next(r for r in evidence["exceptions_2026"] if r["date"] == "2026-11-27")
    assert row["constraint"]["EndTime"] == "1215" and row["constraint"]["TradingDay"] == "Friday"
    start=stamp("2026-11-27T11:00:00-06:00")
    g,clock=special_gate(start,window=CertifiedSpecialHoursWindowV2(date.fromisoformat(row["date"]),time(0),time(12,15)))
    htf=ClosedBarAggregatorV1()
    for i in range(75):
        e=event(i,start)
        clock[0]=e.received_at
        htf.update_completed(g.admit(e).candle())
    assert htf.emitted_counts == {"15m":5,"1h":1}
    assert SessionStateAuthorityV1(g.market_hours).resolve(clock[0],last_closed=g.last_closed).state == "EARLY_CLOSE"
    e=event(75,start)
    clock[0]=e.received_at
    with pytest.raises(ValueError,match="MARKET_HOURS"): g.admit(e)
    assert g.closed_count == 75
    holiday=next(r for r in evidence["exceptions_2026"] if r["date"] == "2026-12-25")
    closed=stamp(holiday["date"]+"T12:00:00-06:00")
    g,_=special_gate(closed,closed=(date.fromisoformat(holiday["date"]),))
    assert SessionStateAuthorityV1(g.market_hours).resolve(closed).state == "HOLIDAY_CLOSED"


def test_snapshot_closed_read_is_side_effect_free_and_cannot_rearm(api_settings,tmp_path):
    start = stamp("2026-09-14T15:58:00-05:00")
    s, clock = service(tmp_path,start)
    deliver(s,clock,event(0,start))
    before = s.get_snapshot()["account_overview"]
    s.control("enable")
    clock[0] = stamp("2026-09-14T16:10:00-05:00")
    for _ in range(3):
        snap = s.get_snapshot()
        assert snap["session_state"]["state"] == "DAILY_MAINTENANCE"
        assert snap["provider_state"] == "CONNECTED"
        assert not snap["paper_ready"] and snap["data_freshness"] == "STALE_OR_MISSING"
        assert snap["account_overview"] == before
        assert snap["sim_execution_authority"] == "DISABLED"
    assert fill_count(s._runtime) == 0
    s.shutdown()


def test_old_forming_relabelled_transport_and_duplicate_first_reopen():
    start=stamp("2026-09-14T15:59:00-05:00")
    reopen=stamp("2026-09-14T17:00:00-05:00")
    g,clock=gate(start)
    g.connection(True)
    g.admit(event(0,start))
    clock[0]=reopen
    old=event(0,start,sequence=1,event_id="old",kind="FORMING_CANDLE",event_time=reopen,received_at=reopen)
    with pytest.raises(ValueError,match="STALE_DATA"): g.admit(old)
    assert g.closed_count == 1
    g,clock=gate(reopen)
    g.connection(True)
    e=event(0,reopen,kind="RAW_EVENT")
    assert g.admit(e) is None and g.admit(e) is None
    assert g.closed_count == 0 and g.duplicate_count == 1


def test_close_boundary_preserves_exit_but_does_not_analyze_or_enter(api_settings,tmp_path,monkeypatch):
    from unittest.mock import Mock
    start=stamp("2026-09-14T15:54:00-05:00")
    s,clock=service(tmp_path,start)
    deliver(s,clock,event(0,start))
    witness(s._runtime)
    s.control("enable")
    for i in range(1,5): deliver(s,clock,event(i,start))
    accounting=s._runtime._paper.runtime
    assert accounting.session.active_position_id is not None
    monkeypatch.setattr(accounting.session.strategy_runner_v2,"run",Mock(side_effect=AssertionError("closed-session strategy")))
    snap=deliver(s,clock,event(5,start,high=10060))
    assert snap["session_state"]["state"] == "DAILY_MAINTENANCE"
    assert snap["completed_trades"] == 1 and fill_count(s._runtime) == 1
    assert not snap["paper_ready"] and snap["latest_decision"] is None
    s.shutdown()


@pytest.mark.parametrize("start_text", ["2026-09-17T15:54:00-05:00", "2026-03-06T15:54:00-06:00", "2026-10-30T15:54:00-05:00"])
def test_multiday_soak_account_journal_gap_equivalence(api_settings,tmp_path,start_text):
    # Known positive decisions are explicit execution witnesses, not score tuning
    # or a claim about the profitability of the real strategy.
    start=stamp(start_text)
    s,clock=service(tmp_path,start)
    deliver(s,clock,event(0,start))
    witness(s._runtime,entries=(5,))
    s.control("enable")
    hours=s.gate.market_hours.get_market_hours_service()
    previous=start
    seq=1
    until=start+timedelta(days=4)
    cursor=start+timedelta(minutes=1)
    closed_checks=0
    while cursor < until:
        clock[0]=cursor+timedelta(minutes=1)
        if hours.is_market_open(symbol="NQ",timestamp=cursor):
            e=event(0,cursor,sequence=seq,event_id=str(seq),high=10060 if seq==5 else 10000)
            snap=deliver(s,clock,e)
            assert s.ingest(e)["account_overview"] == snap["account_overview"]
            previous=cursor
            seq+=1
        else:
            snap=s.get_snapshot()
            assert not snap["paper_ready"]
            closed_checks+=1
        cursor+=timedelta(minutes=1)
    snap=s.get_snapshot()
    runtime=s._runtime._paper.runtime
    assert closed_checks > 0 and previous > start+timedelta(days=3)
    assert s.gate.closed_count == seq and s.gate.duplicate_count == seq-1
    assert fill_count(s._runtime) == snap["completed_trades"] == snap["journal_completed"] == 1
    assert snap["account_overview"]["realized_pnl"] == sum(t.pnl for t in runtime.journal.trades) == 1170
    assert snap["account_overview"]["balance"] == snap["account_overview"]["equity"] == 151170
    import sqlite3
    with sqlite3.connect(tmp_path/"current.sqlite") as db:
        assert db.execute("SELECT count(*) FROM journal").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == seq
    s.shutdown()
