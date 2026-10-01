"""Deterministic certified-factory Current PAPER entry, veto and lifecycle tests."""
from collections import deque
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.market_data.current_candle_authority_v1 import CurrentMarketEventV1
from backend.services import current_paper_economic_news_authority_v1 as news
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2
from backend.tests.test_certified_current_paper_authority_factory_v1 import NOW, _inputs, _create
from backend.tests.test_production_certified_outcome_v17 import api_settings
from backend.tests.test_paper_runtime_sprint08 import fill_count, witness


KEY = b"e"*32
LIVE = dict(status="LIVE",source_adapter_status="LIVE_TAIL",bridge=dict(status="LIVE"))


def setup(tmp_path,monkeypatch,api_settings):
    spec,args,_ = _inputs(tmp_path,monkeypatch,api_settings)
    clock = [NOW-timedelta(minutes=17)]
    args.update(clock=lambda:clock[0],news_root=tmp_path/"news-root",
        l1_directory=tmp_path/"l1-private")
    service = _create(spec,args)
    base = service.entry_authority.news.base
    start = news.utc_us(clock[0]-timedelta(hours=1))
    issued = start+1_000_000
    end = news.utc_us(NOW+timedelta(hours=1))
    value = dict(schema=news.SCHEMA,version=1,**news.identity(base,KEY),
        snapshot_version="e2e.review.1",source_name="test-reviewed-source",
        source_reference="test:explicit-review",source_sha256="7"*64,
        generated_us=start,issued_us=issued,expires_us=end,
        coverage_start_us=start,coverage_end_us=end,
        coverage_intervals=[dict(start_us=start,end_us=end)],
        blackout_before_seconds=300,blackout_after_seconds=300,
        high_impact_events=[])
    payload = news.canonical(value)
    folder = args["news_root"]/"authority-inputs"
    folder.mkdir(parents=True)
    history = dict(schema=news.HISTORY_SCHEMA,identity=news.identity(base,KEY),
        entries=[news.entry(value,payload)])
    for name,raw in zip(news.FILES,(payload,news.sign(payload,KEY),news.history_wire(history,KEY))):
        (folder/name).write_bytes(raw)
    monkeypatch.setattr(news,"read_bounded",lambda path:Path(path).read_bytes())
    monkeypatch.setattr(news.key_store,"load_authority",lambda root:KEY)
    view = dict(status="FRESH",provider="Provider31",contract="NQ DEC26",
        instrument="NQ",quote_age_seconds=0)
    quote = dict(symbol="NQ",bid=10000,ask=10001)
    service.l1_reader.inspect = lambda:(view,quote)
    service.connection(True)
    return service,clock,view,quote


def feed(service,clock,index,*,high=10002,low=9999,close=10000):
    at = NOW-timedelta(minutes=16-index)
    clock[0] = at
    values = dict(provider="NINJATRADER:Provider31",instrument="NQ",contract="NQ DEC26",
        bar_time=at,event_time=at,received_at=at,
        open=10000,high=high,low=low,close=close,volume=10)
    raw = CurrentMarketEventV1(kind="RAW_EVENT",sequence=index*2,event_id=f"raw.{index}",**values)
    closed = CurrentMarketEventV1(kind="CLOSED_CANONICAL_CANDLE",sequence=index*2+1,
        event_id=f"closed.{index}",**values)
    service.ingest(raw)
    if index:
        service.publish_health(coordinator=LIVE,worker_alive=True)
    result = service.ingest(closed)
    service.publish_health(coordinator=LIVE,worker_alive=True)
    return result


def deltas(service):
    runtime = service._runtime
    life = runtime._paper.runtime.lifecycle
    broker = life.broker_connector_v2
    return (len(broker.get_orders()),len(broker.get_fills()),
        len(life.get_active_positions()),len(runtime._paper.runtime.journal.trades))


def warm(service,clock):
    feed(service,clock,0)
    service.control("enable")
    for index in range(1,15):
        feed(service,clock,index)
    witness(service._runtime,entries=(16,))


def test_factory_signed_news_health_enable_one_entry_and_sl_exit(tmp_path,monkeypatch,api_settings):
    service,clock,_,_ = setup(tmp_path,monkeypatch,api_settings)
    with pytest.raises(RuntimeError):
        service.control("enable")
    warm(service,clock)
    before = deltas(service)
    snap = feed(service,clock,15)
    after = deltas(service)
    assert tuple(b-a for a,b in zip(before,after))[:2] == (1,1)
    assert snap["execution_state"] == "OPEN"
    feed(service,clock,16,low=9960)
    assert service.get_snapshot()["execution_state"] == "FLAT"
    assert service.get_snapshot()["completed_trades"] == 1
    assert service.get_snapshot()["journal_completed"] == 1


def test_tp_exit_then_later_valid_reentry_without_per_trade_approval(tmp_path,monkeypatch,api_settings):
    service,clock,_,_ = setup(tmp_path,monkeypatch,api_settings)
    warm(service,clock)
    witness(service._runtime,entries=(16,18))
    feed(service,clock,15)
    assert service.get_snapshot()["execution_state"] == "OPEN"
    feed(service,clock,16,high=10070)
    assert service.get_snapshot()["execution_state"] == "FLAT"
    assert service.get_snapshot()["completed_trades"] == 1
    assert service.get_snapshot()["journal_completed"] == 1
    before=deltas(service)
    feed(service,clock,17,close=10001)
    after=deltas(service)
    assert after[0] == before[0]+1
    assert after[1] == before[1]+1
    assert service.get_snapshot()["execution_state"] == "OPEN"
    assert service._runtime._enabled is True


@pytest.mark.parametrize("veto", ["news_missing","news_expired","news_coverage",
    "news_blackout","quote_missing","quote_stale","quote_invalid","quote_crossed",
    "quote_provider","quote_contract","spread","atr_not_ready","atr_low",
    "signal_old","stop_small","stop_large","rr_low","probability",
    "confluence","risk","market_closed","max_position","duplicate"])
def test_each_rejected_candidate_has_zero_financial_deltas(tmp_path,monkeypatch,api_settings,veto):
    service,clock,view,quote = setup(tmp_path,monkeypatch,api_settings)
    warm(service,clock)
    entry = service.entry_authority
    runtime = service._runtime
    life = runtime._paper.runtime.lifecycle
    if veto.startswith("news_"):
        reason = {"news_missing":"PACKAGE_MISSING","news_expired":"EXPIRED",
            "news_coverage":"OUTSIDE_CERTIFIED_COVERAGE","news_blackout":"HIGH_IMPACT_BLOCK"}[veto]
        entry.news.inspect = lambda **_:dict(status=reason,reason=reason,blocked=True)
    if veto == "quote_missing": service.l1_reader.inspect = lambda:(dict(view,status="WAITING"),None)
    if veto == "quote_stale": view["status"] = "STALE"
    if veto == "quote_invalid": quote["bid"] = float("nan")
    if veto == "quote_crossed": quote["ask"] = 9999
    if veto == "quote_provider": view["provider"] = "OTHER"
    if veto == "quote_contract": view["contract"] = "OTHER"
    if veto == "spread": quote["ask"] = 10006
    if veto == "atr_not_ready": entry.rows.clear()
    if veto == "atr_low":
        entry.rows = deque((replace(r,ohlcv=(10000,10000.25,10000,10000,10))
            for r in list(entry.rows)),maxlen=15)
    if veto == "signal_old": entry.clock = lambda:clock[0]+timedelta(seconds=301)
    if veto in ("stop_small","stop_large","rr_low","probability","confluence"):
        def strategy(context):
            price=context["candle"]["close"]
            metadata=dict(stop_loss=price-30,take_profit=price+60,
                confluence_score=.95,grade="A+",reasons=[])
            action=TradingActionV2.BUY
            if veto == "stop_small": metadata["stop_loss"] = price-.5
            if veto == "stop_large":
                action=TradingActionV2.SELL
                metadata.update(stop_loss=price+101,take_profit=price-210)
            if veto == "rr_low": metadata["take_profit"] = price+30
            if veto == "confluence": metadata["confluence_score"] = .79
            return TradingDecisionV2(action,.79 if veto=="probability" else .95,
                "test veto",metadata)
        runtime._paper.runtime.session.strategy_runner_v2.run=strategy
    if veto == "risk":
        life.execution_risk_gate_v1.evaluate_trade = Mock(return_value={"execution":"BLOCKED"})
    if veto == "market_closed":
        entry.gate.reasons = lambda:["SESSION_CLOSED"]
    if veto == "max_position":
        life.get_active_positions = lambda:[{"position_id":"prior"}]
    if veto == "duplicate":
        life._reserve_submission = lambda **_:False
    before = deltas(service)
    feed(service,clock,15)
    assert deltas(service) == before
