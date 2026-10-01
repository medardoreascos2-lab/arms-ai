"""Independent current-only automatic-entry vetoes; no account or submit."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.backtesting.current_paper_entry_authority_v1 import CurrentPaperEntryAuthorityV1
from backend.market_data.current_candle_authority_v1 import CurrentClosedObservationV1
from backend.strategies.trading_strategy_v2 import TradingActionV2, TradingDecisionV2


NOW = datetime(2026, 10, 1, 14, tzinfo=timezone.utc)


def settings():
    return SimpleNamespace(maximum_quote_age_seconds=30, maximum_spread_points=5,
        minimum_atr_points=1, maximum_signal_age_seconds=300,
        minimum_stop_points=1, maximum_stop_points=100,
        minimum_reward_risk_ratio=2, minimum_a_plus_probability=.8,
        minimum_a_plus_confluence_score=.8, maximum_open_positions=1)


def row(index, *, ohlcv=(100,102,99,100,10)):
    available = NOW - timedelta(minutes=14-index)
    return CurrentClosedObservationV1("NINJATRADER:Provider31", "NQ DEC26",
        available-timedelta(minutes=1), available, available, available,
        index, str(index), "a"*64, "b"*64, "NQ", "row", ohlcv,
        available.date().isoformat())


def setup():
    gate = SimpleNamespace(digest="b"*64, reasons=lambda: [])
    news = SimpleNamespace(inspect=lambda **_: dict(status="CERTIFIED_CLEAR",blocked=False))
    view = dict(status="FRESH", provider="Provider31",contract="NQ DEC26",
        instrument="NQ",quote_age_seconds=0)
    quote = dict(symbol="NQ",bid=100,ask=101)
    l1 = SimpleNamespace(inspect=lambda: (view,quote))
    clock = [NOW]
    owner = CurrentPaperEntryAuthorityV1(gate=gate,news=news,l1=l1,
        settings=settings(),clock=lambda:clock[0])
    for i in range(15):
        owner.observe(row(i))
    decision = TradingDecisionV2(TradingActionV2.BUY,.9,"A+",
        dict(stop_loss=95,take_profit=110,confluence_score=.9))
    return owner, gate, news, l1, clock, decision


def inspect(owner, decision, *, positions=0):
    return owner.inspect(row=owner.rows[-1],decision=decision,open_positions=positions)


def test_all_current_evidence_clear():
    owner, _, _, _, _, decision = setup()
    assert inspect(owner,decision) == []


@pytest.mark.parametrize("status,expected", [
    ("PACKAGE_MISSING","NEWS_MISSING"),("EXPIRED","NEWS_EXPIRED"),
    ("OUTSIDE_CERTIFIED_COVERAGE","NEWS_OUTSIDE_COVERAGE"),
    ("HIGH_IMPACT_BLOCK","NEWS_BLACKOUT")])
def test_news_veto(status,expected):
    owner, _, news, _, _, decision = setup()
    news.inspect = lambda **_: dict(status=status,reason=status,blocked=True)
    assert expected in inspect(owner,decision)


@pytest.mark.parametrize("change,expected", [
    ("missing","QUOTE_MISSING"),("stale","QUOTE_STALE"),
    ("invalid","QUOTE_INVALID"),("crossed","QUOTE_CROSSED"),
    ("provider","QUOTE_WRONG_PROVIDER"),("contract","QUOTE_WRONG_CONTRACT"),
    ("spread","SPREAD_TOO_WIDE"),("revoked","QUOTE_REVOKED")])
def test_l1_veto(change,expected):
    owner, _, _, l1, _, decision = setup()
    view, quote = l1.inspect()
    view, quote = dict(view),dict(quote)
    if change == "missing": quote = None
    if change == "stale": view["status"] = "STALE"
    if change == "invalid": quote["bid"] = float("nan")
    if change == "crossed": quote["ask"] = 99
    if change == "provider": view["provider"] = "OTHER"
    if change == "contract": view["contract"] = "OTHER"
    if change == "spread": quote["ask"] = 106
    if change == "revoked": view["status"] = "REVOKED"
    l1.inspect = lambda: (view,quote)
    assert expected in inspect(owner,decision)


def test_atr_not_ready_and_too_low():
    owner, _, _, _, _, decision = setup()
    owner.rows.pop()
    assert "ATR_NOT_READY" in inspect(owner,decision)
    owner, _, _, _, _, decision = setup()
    owner.rows.clear()
    for i in range(15):
        owner.observe(row(i,ohlcv=(100,100.25,100,100,10)))
    assert "ATR_TOO_LOW" in inspect(owner,decision)


@pytest.mark.parametrize("field,value,expected", [
    ("stop_loss",99.5,"STOP_TOO_SMALL"),("stop_loss",-5,"STOP_INVALID"),
    ("stop_loss",1,"RR_TOO_LOW"),("take_profit",105,"RR_TOO_LOW")])
def test_plan_veto(field,value,expected):
    owner, _, _, _, _, decision = setup()
    decision.metadata[field] = value
    assert expected in inspect(owner,decision)


def test_stop_too_large_on_short_plan():
    owner, _, _, _, _, decision = setup()
    decision.action = TradingActionV2.SELL
    decision.metadata.update(stop_loss=201,take_profit=90)
    assert "STOP_TOO_LARGE" in inspect(owner,decision)


def test_signal_probability_confluence_market_and_position_vetoes():
    owner, gate, _, _, clock, decision = setup()
    clock[0] += timedelta(seconds=301)
    assert "SIGNAL_TOO_OLD" in inspect(owner,decision)
    clock[0] = NOW
    decision.confidence = .79
    assert "PROBABILITY_TOO_LOW" in inspect(owner,decision)
    decision.confidence = .9
    decision.metadata["confluence_score"] = .79
    assert "CONFLUENCE_TOO_LOW" in inspect(owner,decision)
    decision.metadata["confluence_score"] = .9
    gate.reasons = lambda: ["SESSION_CLOSED"]
    assert "MARKET_CLOSED_OR_UNAVAILABLE" in inspect(owner,decision)
    gate.reasons = lambda: []
    assert "MAX_POSITION_REACHED" in inspect(owner,decision,positions=1)
