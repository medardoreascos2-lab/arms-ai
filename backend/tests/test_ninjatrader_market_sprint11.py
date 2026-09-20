"""Synthetic protocol conformance, not native feed/account certification."""
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest

from backend.api.ninjatrader_market_app_v1 import create_ninjatrader_market_app_v1
from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.config.api_settings import APISettings
from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1, SCHEMA
from backend.tests.test_current_paper_sprint10 import gate, START, config, api_settings
from backend.tests.test_paper_runtime_sprint08 import witness, fill_count

SESSION = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def setup(tmp_path):
    g, clock = gate(label="CLOSE")
    g = type(g)(contract=replace(g.contract, provider="NINJATRADER:SYNTHETIC_FIXTURE"),
        market_hours=g.market_hours, maximum_age_seconds=g.maximum_age, clock=g.clock)
    s = CurrentPaperServiceV1(gate=g, config=config(), settings=APISettings(),
        state_path=tmp_path/"paper.sqlite", initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
    path = tmp_path/"stream.jsonl"
    path.touch()
    reader = NinjaTraderMarketReaderV1(service=s, path=path, provider="SYNTHETIC_FIXTURE", expiry="2026-12-18")
    return reader, clock


def frame(clock, seq, kind="HEARTBEAT", payload=None):
    return dict(schema=SCHEMA, session=SESSION, sequence=seq, event_time=clock[0].isoformat(),
                kind=kind, payload={"connected": True} if payload is None else payload)


def hello(r, clock):
    c = r.service.gate.contract
    return frame(clock, 0, "HELLO", dict(provider="SYNTHETIC_FIXTURE", contract=c.contract,
        expiry="2026-12-18", instrument="NQ", tick_size=.25, point_value=20, timeframe="1m",
        trading_hours_template=c.trading_hours_template, source_timezone="UTC", bar_label="CLOSE",
        realtime=True, read_only=True))


def bar(clock, seq, kind="CLOSED", **changes):
    payload = dict(bar_time=clock[0].isoformat(), open=10000, high=10000, low=10000, close=10000, volume=10)
    payload.update(changes)
    return frame(clock, seq, kind, payload)


def send(r, f):
    with r.path.open("ab") as stream:
        stream.write((json.dumps(f)+"\n").encode())
    return r.poll()


def tick_to(r, clock, target):
    while clock[0] < target:
        clock[0] = min(clock[0]+timedelta(seconds=5), target)
        send(r, frame(clock, r.sequence+1))


def test_closed_only_htf_strategy_dashboard_zero_execution(api_settings, tmp_path, monkeypatch):
    r, clock = setup(tmp_path)
    send(r, hello(r, clock))
    send(r, bar(clock, 1, "FORMING", bar_time=(clock[0]+timedelta(minutes=1)).isoformat()))
    assert r.service._runtime is None and r.service.gate.closed_count == 0
    for i in range(120):
        tick_to(r, clock, START+timedelta(minutes=i+1))
        snap = send(r, bar(clock, r.sequence+1))
    runtime = r.service._runtime
    assert snap["htf_emitted"] == {"15m":8, "1h":2}
    assert r.service.gate.closed_count == 120
    assert snap["completed_trades"] == snap["journal_completed"] == fill_count(runtime) == 0
    assert runtime._paper.runtime.index == 120
    assert runtime._last_decision is not None
    account = snap["account_overview"]
    monkeypatch.setattr(r, "poll", Mock(return_value=snap))
    monkeypatch.setattr(r.service, "ingest", Mock(side_effect=AssertionError("GET mutated")))
    with TestClient(create_ninjatrader_market_app_v1(reader=r)) as client:
        for _ in range(3):
            result = client.get("/api/v2/backtesting/dashboard").json()["paper_research"]
            assert result["account_overview"] == account
            assert result["external_order_authority"] is False
            assert result["external_account_class"] == "NOT_DISCOVERED"
        assert client.post("/api/v2/paper/enable").status_code == 404
        assert client.post("/api/v2/submit_order").status_code == 404


@pytest.mark.parametrize("mutation", [
    lambda f: f.update(schema="unknown"),
    lambda f: f.update(sequence=True),
    lambda f: f.update(sequence=2),
    lambda f: f.update(session="not-a-session"),
    lambda f: f.update(session=123),
    lambda f: f.update(event_time="2026-09-14T14:01:00"),
    lambda f: f.update(event_time="2026-09-14T14:02:00+00:00"),
    lambda f: f["payload"].update(realtime=False),
    lambda f: f["payload"].update(read_only=1),
    lambda f: f["payload"].update(contract="OTHER"),
    lambda f: f["payload"].update(expiry="2026-09-18"),
    lambda f: f["payload"].update(source_timezone="LOCAL"),
    lambda f: f["payload"].update(bar_label="OPEN"),
    lambda f: f["payload"].update(tick_size=1),
    lambda f: f["payload"].update(point_value=2),
    lambda f: f["payload"].update(trading_hours_template="UNKNOWN"),
    lambda f: f["payload"].update(account="FORBIDDEN_EXTRA_FIELD"),
])
def test_invalid_header_latches_without_account(api_settings, tmp_path, mutation):
    r, clock = setup(tmp_path)
    f = hello(r, clock)
    mutation(f)
    with pytest.raises(ValueError): send(r, f)
    assert r.service._runtime is None and not r.get_snapshot()["provider_transport"]["connected"]
    assert "RECOVERY_REQUIRED" in r.service.gate.reasons()
    with pytest.raises(RuntimeError): r.poll()
    r.close()


@pytest.mark.parametrize("case", ["duplicate", "sequence_gap", "session_change", "disconnect", "heartbeat_timeout",
    "heartbeat_lie", "truncate", "replacement", "bar_gap", "future_close", "bad_tick", "bool_price", "bad_volume"])
def test_fault_after_close_never_duplicates_or_reconnects(api_settings, tmp_path, case):
    r, clock = setup(tmp_path)
    send(r, hello(r, clock))
    first = bar(clock, 1)
    send(r, first)
    account = r.service.get_snapshot()["account_overview"]
    f = frame(clock, 2)
    if case == "duplicate": f = first
    if case == "sequence_gap": f["sequence"] = 3
    if case == "session_change": f["session"] = "ffffffff-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    if case == "disconnect": f["kind"] = "DISCONNECTED"
    if case == "heartbeat_lie": f["payload"] = {"connected": 1}
    if case == "heartbeat_timeout": clock[0] += timedelta(seconds=16)
    if case == "truncate": r.path.write_bytes(b"")
    if case == "replacement":
        replacement = tmp_path/"new.jsonl"
        replacement.write_bytes(r.path.read_bytes())
        # Windows denies replacement of an open read handle; a failed replacement
        # is itself OS containment. Reader identity check covers supported platforms.
        try: replacement.replace(r.path)
        except PermissionError:
            r.close()
            return
    if case in {"bar_gap", "future_close", "bad_tick", "bool_price", "bad_volume"}:
        tick_to(r, clock, clock[0]+timedelta(minutes=2 if case == "bar_gap" else 1))
        f = bar(clock, r.sequence+1)
        if case == "future_close": f["payload"]["bar_time"] = (clock[0]+timedelta(minutes=1)).isoformat()
        if case == "bad_tick": f["payload"]["open"] = 10000.1
        if case == "bool_price": f["payload"]["open"] = True
        if case == "bad_volume": f["payload"]["volume"] = 1.5
    with pytest.raises(ValueError): send(r, f)
    assert r.service.gate.closed_count == 1
    assert r.service.get_snapshot()["account_overview"] == account
    assert fill_count(r.service._runtime) == 0
    with pytest.raises(RuntimeError): r.service.control("enable")
    r.close()


@pytest.mark.parametrize("raw", [b'{"schema":1,"schema":2}\n', b'NaN\n', b'[]\n', b'x'*16385, b'\xff\n'])
def test_invalid_wire_never_ingests(api_settings, tmp_path, raw):
    r, clock = setup(tmp_path)
    r.path.write_bytes(raw)
    with pytest.raises(ValueError): r.poll()
    assert r.service._runtime is None
    r.close()


def test_partial_line_waits_but_does_not_extend_heartbeat(api_settings, tmp_path):
    r, clock = setup(tmp_path)
    data = json.dumps(hello(r, clock)).encode()
    r.path.write_bytes(data[:40])
    r.poll()
    assert r.session is None
    with r.path.open("ab") as stream: stream.write(data[40:]+b"\n")
    r.poll()
    assert r.session == SESSION
    clock[0] += timedelta(seconds=16)
    assert not r.get_snapshot()["provider_transport"]["connected"]
    with pytest.raises(ValueError): r.poll()
    r.close()


def test_even_positive_fixture_decision_cannot_execute_in_smoke(api_settings, tmp_path):
    r, clock = setup(tmp_path)
    send(r, hello(r, clock))
    send(r, bar(clock, 1))
    witness(r.service._runtime)
    for i in range(1,8):
        tick_to(r, clock, START+timedelta(minutes=i+1))
        r.service.control("enable")  # An erroneous in-process caller cannot grant smoke authority.
        send(r, bar(clock, r.sequence+1))
    assert fill_count(r.service._runtime) == 0
    assert not r.service._runtime._enabled
    r.close()


def test_native_exporter_has_no_order_channel_and_skips_historical_partial_bars():
    source = (Path(__file__).resolve().parents[2]/"integrations/ninjatrader/ArmsReadOnlyMarketV1.cs").read_text()
    for forbidden in ("Account.All", "Submit(", "CreateOrder(", "AtmStrategy", "TcpClient", "HttpClient", "NinjaTrader.Client"):
        assert forbidden not in source
    assert 'CurrentBar - 1 > firstRealtimeBar' in source
    assert 'Emit("CLOSED", Candle(1))' in source
    assert 'State != State.Realtime' in source
    assert 'Calculate.OnEachTick' in source
    assert 'FileMode.CreateNew' in source
