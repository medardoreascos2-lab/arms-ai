"""Offline Current PAPER news signature, identity and time-bound adversarial tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from backend.services import current_paper_economic_news_authority_v1 as news


NOW = datetime(2026, 10, 1, 14, tzinfo=timezone.utc)
KEY = b"p" * 32
BASE = news.binding(reviewed_spec_sha256="1" * 64,
    feed_contract_sha256="2" * 64, paper_config_sha256="3" * 64,
    run_namespace_sha256="4" * 64)


def candidate(*, at=NOW, events=None, **changes):
    now = news.utc_us(at)
    value = dict(schema=news.SCHEMA, version=1, **news.identity(BASE, KEY),
        snapshot_version="review.1", source_name="reviewed-source",
        source_reference="operator:review.1", source_sha256="5" * 64,
        generated_us=now-1_200_000_000, issued_us=now-900_000_000,
        expires_us=now+3_600_000_000, coverage_start_us=now-900_000_000,
        coverage_end_us=now+3_600_000_000,
        coverage_intervals=[dict(start_us=now-900_000_000,end_us=now+3_600_000_000)],
        blackout_before_seconds=300, blackout_after_seconds=300,
        high_impact_events=[] if events is None else events)
    value.update(changes)
    return news.canonical(value)


def fixture(tmp_path, monkeypatch, *, raw=None):
    root = tmp_path / "current-paper-news"
    folder = root / "authority-inputs"
    folder.mkdir(parents=True)
    payload = candidate() if raw is None else raw
    value = news.parse(payload)
    history = dict(schema=news.HISTORY_SCHEMA, identity=news.identity(BASE, KEY),
        entries=[news.entry(value,payload)])
    for name, content in zip(news.FILES,
            (payload, news.sign(payload,KEY), news.history_wire(history,KEY))):
        (folder/name).write_bytes(content)
    monkeypatch.setattr(news, "read_bounded", lambda path: Path(path).read_bytes())
    monkeypatch.setattr(news.key_store, "load_authority", lambda root: KEY)
    clock = [NOW]
    owner = news.CurrentPaperEconomicNewsAuthorityV1(base=BASE, clock=lambda: clock[0], root=root)
    return owner, clock, folder


def test_valid_signed_clear_and_certified_empty_calendar(tmp_path, monkeypatch):
    owner, _, _ = fixture(tmp_path, monkeypatch)
    assert owner.inspect()["status"] == "CERTIFIED_CLEAR"
    assert owner.inspect(symbol="OTHER")["blocked"] is True


@pytest.mark.parametrize("change", ["missing", "signature", "wrong_identity", "expired",
    "future", "coverage", "rollback", "publication_lock", "publication_change"])
def test_invalid_authority_fails_closed(tmp_path, monkeypatch, change):
    owner, clock, folder = fixture(tmp_path, monkeypatch)
    if change == "missing":
        (folder/news.FILES[0]).unlink()
    elif change == "signature":
        (folder/news.FILES[1]).write_bytes(b"0"*64)
    elif change == "wrong_identity":
        owner.base = {**BASE, "feed_contract_sha256":"6"*64}
    elif change == "expired":
        clock[0] += timedelta(hours=2)
    elif change == "future":
        owner, clock, folder = fixture(tmp_path/"second", monkeypatch,
            raw=candidate(issued_us=news.utc_us(NOW)+1_000_000))
    elif change == "coverage":
        clock[0] += timedelta(hours=1)
    elif change == "rollback":
        history = news.parse((folder/news.FILES[2]).read_bytes())
        history["history"]["entries"][-1]["sha256"] = "0"*64
        (folder/news.FILES[2]).write_bytes(news.canonical(history))
    elif change == "publication_lock":
        (folder/news.LOCK).write_bytes(b"")
    elif change == "publication_change":
        original = news.read_bounded
        calls = [0]
        def changed(path):
            calls[0] += 1
            return b"changed" if calls[0] == 4 else original(path)
        monkeypatch.setattr(news, "read_bounded", changed)
    assert owner.inspect()["blocked"] is True


@pytest.mark.parametrize("offset,blocked", [(-300,True),(300,True),(-301,False),(301,False)])
def test_blackout_boundaries_are_inclusive(tmp_path, monkeypatch, offset, blocked):
    event_at = NOW + timedelta(seconds=-offset)
    event = dict(event_id="usd.1",name="High USD",event_us=news.utc_us(event_at),
        impact="HIGH",currency="USD")
    owner, _, _ = fixture(tmp_path, monkeypatch, raw=candidate(events=[event]))
    assert owner.inspect()["blocked"] is blocked


def test_version_conflict_and_domain_signature_are_rejected():
    payload = candidate()
    assert news.sign(payload,KEY) != news.sign(payload,KEY,domain=b"arms.sim-native.economic-news.v1\0")
    history = dict(schema=news.HISTORY_SCHEMA, identity=news.identity(BASE,KEY),
        entries=[news.entry(news.parse(payload),payload)]*2)
    with pytest.raises(ValueError, match="HISTORY_INVALID"):
        news.verify_history(news.history_wire(history,KEY),base=BASE,key=KEY)


def test_wrong_contract_and_non_high_usd_rejected():
    payload = candidate(contract="ES DEC26")
    with pytest.raises(ValueError, match="PACKAGE_BINDING"):
        news.verify(payload,news.sign(payload,KEY),base=BASE,key=KEY,now=NOW)
    event = dict(event_id="usd.1",name="Low USD",event_us=news.utc_us(NOW),
        impact="LOW",currency="USD")
    payload = candidate(events=[event])
    with pytest.raises(ValueError, match="EVENT_SCHEMA"):
        news.verify(payload,news.sign(payload,KEY),base=BASE,key=KEY,now=NOW)
