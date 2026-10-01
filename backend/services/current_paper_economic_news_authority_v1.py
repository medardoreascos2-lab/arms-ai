"""Operator-published Current PAPER news evidence; never SIM_NATIVE clearance.

The signature attests an ARMS-reviewed candidate, not independent vendor truth.
Publication is explicit. Runtime inspection only reads and fails closed.
"""
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import os
from pathlib import Path
import re
import subprocess

from backend.services import sim_native_authority_v3 as key_store
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_market_hours_authority_v1 import (
    canonical, parse, read_bounded, require,
)


SCHEMA = "ARMS_CURRENT_PAPER_ECONOMIC_NEWS_AUTHORITY_V1"
HISTORY_SCHEMA = "ARMS_CURRENT_PAPER_ECONOMIC_NEWS_HISTORY_V1"
DOMAIN = b"arms.current-paper.economic-news.v1\0"
HISTORY_DOMAIN = b"arms.current-paper.economic-news.history.v1\0"
FILES = ("economic-news-v1.json", "economic-news-v1.sig", "economic-news-history-v1.json")
LOCK = "economic-news-publish.lock"
MAX_LIFE_US = 86_400_000_000
BEFORE = AFTER = 300
NEWS_POLICY_ID = sha256(canonical(dict(schema=SCHEMA, version=1,
    blackout_before_seconds=BEFORE, blackout_after_seconds=AFTER,
    boundaries="INCLUSIVE", impact="HIGH", currency="USD",
    max_life_us=MAX_LIFE_US))).hexdigest()
BASE_FIELDS = frozenset(("execution_domain provider contract instrument reviewed_spec_sha256 "
    "feed_contract_sha256 paper_config_sha256 run_namespace_sha256").split())
EXPECTED = dict(execution_domain="CURRENT_MARKET_PAPER", provider="NINJATRADER:Provider31",
    contract="NQ DEC26", instrument="NQ")
EVENT_FIELDS = frozenset("event_id name event_us impact currency".split())
FIELDS = BASE_FIELDS | frozenset(("schema version authority_id news_policy_id snapshot_version "
    "source_name source_reference source_sha256 generated_us issued_us expires_us "
    "coverage_start_us coverage_end_us coverage_intervals blackout_before_seconds "
    "blackout_after_seconds high_impact_events").split())


def default_root():
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise ValueError("WINDOWS_LOCAL_AUTHORITY_ROOT_REQUIRED")
    return key_store.safe_path(Path(os.environ["LOCALAPPDATA"]) / "ARMS-AI" /
        "current-paper-news-v1", authority=True)


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _text(value):
    return (type(value) is str and 0 < len(value) <= 512 and value.strip() == value
        and all(32 <= ord(char) < 127 for char in value))


def _identifier(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value) is not None


def binding(*, reviewed_spec_sha256, feed_contract_sha256, paper_config_sha256,
            run_namespace_sha256):
    value = {**EXPECTED, "reviewed_spec_sha256": reviewed_spec_sha256,
        "feed_contract_sha256": feed_contract_sha256,
        "paper_config_sha256": paper_config_sha256,
        "run_namespace_sha256": run_namespace_sha256}
    require(all(_hash(value[name]) for name in BASE_FIELDS - EXPECTED.keys()), "PAPER_BINDING_INVALID")
    return value


def runtime_binding(*, reviewed_spec_sha256, gate, config, state_path):
    """Recompute identity from the actual certified factory inputs."""
    return binding(reviewed_spec_sha256=reviewed_spec_sha256,
        feed_contract_sha256=gate.digest,
        paper_config_sha256=sha256(canonical(asdict(config))).hexdigest(),
        run_namespace_sha256=sha256(str(Path(state_path).parent.resolve()).encode("utf-8")).hexdigest())


def identity(base, key):
    require(type(base) is dict and set(base) == BASE_FIELDS, "PAPER_BINDING_INVALID")
    expected = binding(**{name: base[name] for name in BASE_FIELDS - EXPECTED.keys()})
    require(base == expected, "PAPER_BINDING_INVALID")
    require(type(key) is bytes and len(key) == 32, "AUTHORITY_KEY_INVALID")
    return {**base, "authority_id": key_store.authority_id(key), "news_policy_id": NEWS_POLICY_ID}


def sign(payload, key, *, domain=DOMAIN):
    return hmac.new(key, domain + payload, sha256).hexdigest().encode("ascii")


def covered(value, at):
    return any(row["start_us"] <= at <= row["end_us"] for row in value["coverage_intervals"])


def verify(payload, signature, *, base, key, now):
    require(type(signature) is bytes and hmac.compare_digest(signature, sign(payload, key)), "HMAC_INVALID")
    value = parse(payload)
    require(type(value) is dict and set(value) == FIELDS and canonical(value) == payload, "PACKAGE_SCHEMA")
    require(value["schema"] == SCHEMA and type(value["version"]) is int and value["version"] == 1,
        "PACKAGE_VERSION")
    require(all(type(value[name]) is type(expected) and value[name] == expected
        for name, expected in identity(base, key).items()), "PACKAGE_BINDING")
    require(type(value["blackout_before_seconds"]) is int and value["blackout_before_seconds"] == BEFORE
        and type(value["blackout_after_seconds"]) is int and value["blackout_after_seconds"] == AFTER,
        "NEWS_POLICY_MISMATCH")
    require(_identifier(value["snapshot_version"]), "SNAPSHOT_VERSION")
    require(_text(value["source_name"]) and _text(value["source_reference"])
        and _hash(value["source_sha256"]), "SOURCE_METADATA")
    times = ("generated_us", "issued_us", "expires_us", "coverage_start_us", "coverage_end_us")
    require(all(type(value[name]) is int and 0 < value[name] <= 253402300799999999
        for name in times), "PACKAGE_TIME")
    now_us = utc_us(now)
    require(value["generated_us"] <= value["issued_us"] <= now_us, "FUTURE_PACKAGE")
    require(0 < value["expires_us"] - value["issued_us"] <= MAX_LIFE_US, "PACKAGE_LIFETIME")
    require(value["coverage_start_us"] <= value["coverage_end_us"]
        and value["expires_us"] <= value["coverage_end_us"], "COVERAGE_INVALID")
    require(now_us < value["expires_us"], "EXPIRED")
    intervals = value["coverage_intervals"]
    require(type(intervals) is list and 0 < len(intervals) <= 128, "COVERAGE_INVALID")
    prior = None
    for row in intervals:
        require(type(row) is dict and set(row) == {"start_us", "end_us"}, "COVERAGE_INVALID")
        start, end = row["start_us"], row["end_us"]
        require(type(start) is int and type(end) is int and
            value["coverage_start_us"] <= start <= end <= value["coverage_end_us"]
            and (prior is None or start > prior), "COVERAGE_INVALID")
        prior = end
    require(intervals[0]["start_us"] == value["coverage_start_us"]
        and intervals[-1]["end_us"] == value["coverage_end_us"], "COVERAGE_INVALID")
    events = value["high_impact_events"]
    require(type(events) is list and len(events) <= 1024, "EVENT_SCHEMA")
    ids, event_identities = set(), set()
    for event in events:
        require(type(event) is dict and set(event) == EVENT_FIELDS, "EVENT_SCHEMA")
        require(_identifier(event["event_id"]) and _text(event["name"])
            and event["impact"] == "HIGH" and event["currency"] == "USD"
            and type(event["event_us"]) is int and covered(value, event["event_us"]), "EVENT_SCHEMA")
        event_identity = (event["event_us"], event["name"], event["currency"])
        require(event["event_id"] not in ids and event_identity not in event_identities,
            "EVENT_CONFLICT")
        ids.add(event["event_id"])
        event_identities.add(event_identity)
    return value


def entry(value, payload):
    return dict(snapshot_version=value["snapshot_version"], issued_us=value["issued_us"],
        sha256=sha256(payload).hexdigest())


def history_wire(history, key):
    return canonical(dict(history=history,
        signature=sign(canonical(history), key, domain=HISTORY_DOMAIN).decode("ascii")))


def verify_history(raw, *, base, key):
    envelope = parse(raw)
    require(type(envelope) is dict and set(envelope) == {"history", "signature"}
        and canonical(envelope) == raw, "HISTORY_INVALID")
    history = envelope["history"]
    require(type(envelope["signature"]) is str and hmac.compare_digest(
        envelope["signature"].encode("ascii"),
        sign(canonical(history), key, domain=HISTORY_DOMAIN)), "HISTORY_INVALID")
    require(type(history) is dict and set(history) == {"schema", "identity", "entries"}
        and history["schema"] == HISTORY_SCHEMA and history["identity"] == identity(base, key),
        "HISTORY_INVALID")
    require(type(history["entries"]) is list and 0 < len(history["entries"]) <= 512,
        "HISTORY_INVALID")
    prior, versions = 0, set()
    for row in history["entries"]:
        require(type(row) is dict and set(row) == {"snapshot_version", "issued_us", "sha256"}
            and _identifier(row["snapshot_version"]) and row["snapshot_version"] not in versions
            and type(row["issued_us"]) is int and row["issued_us"] > prior
            and _hash(row["sha256"]), "HISTORY_INVALID")
        prior = row["issued_us"]
        versions.add(row["snapshot_version"])
    return history


class CurrentPaperEconomicNewsAuthorityV1:
    """Pure fail-closed lookup. No provisioning, renewal, or network access."""

    def __init__(self, *, base, clock, root=None):
        if not callable(clock):
            raise TypeError("EXPLICIT_CLOCK_REQUIRED")
        self.base = dict(base)
        self.clock = clock
        self.root = key_store.safe_path(root, authority=True) if root is not None else default_root()

    @staticmethod
    def unavailable(reason="AUTHORITY_UNAVAILABLE"):
        return dict(status="UNAVAILABLE", reason=reason, covered=False, blocked=True,
            news_policy_id=NEWS_POLICY_ID)

    def inspect(self, *, symbol="NQ", timestamp=None):
        try:
            before = self.clock()
            before_us = utc_us(before)
            folder = self.root / "authority-inputs"
            require(not (folder / LOCK).exists(), "PUBLICATION_IN_PROGRESS")
            payload, signature, history_raw = [read_bounded(folder / name) for name in FILES]
            key = key_store.load_authority(self.root)
            after = self.clock()
            after_us = utc_us(after)
            require(after_us >= before_us, "CLOCK_REGRESSION")
            value = verify(payload, signature, base=self.base, key=key, now=after)
            history = verify_history(history_raw, base=self.base, key=key)
            require(history["entries"][-1] == entry(value, payload), "ROLLBACK_OR_CONFLICT")
            require(not (folder / LOCK).exists()
                and history_raw == read_bounded(folder / FILES[2]), "PUBLICATION_CHANGED")
            final_us = utc_us(self.clock())
            require(final_us >= after_us, "CLOCK_REGRESSION")
            require(value["issued_us"] <= final_us < value["expires_us"], "EXPIRED")
            require(symbol == "NQ", "UNSUPPORTED_SYMBOL")
            at = before_us if timestamp is None else utc_us(timestamp)
            require(value["issued_us"] <= at <= final_us and at < value["expires_us"],
                "EVALUATION_TIME")
            in_coverage = covered(value, at) and covered(value, final_us)
            blackout = any(event["event_us"] - BEFORE * 1_000_000 <= instant
                <= event["event_us"] + AFTER * 1_000_000
                for event in value["high_impact_events"] for instant in (at, final_us))
            blocked = not in_coverage or blackout
            status = ("OUTSIDE_CERTIFIED_COVERAGE" if not in_coverage else
                "HIGH_IMPACT_BLOCK" if blackout else "CERTIFIED_CLEAR")
            return dict(status=status, reason=status if blocked else None,
                covered=in_coverage, blocked=blocked, news_policy_id=NEWS_POLICY_ID,
                snapshot_version=value["snapshot_version"], expires_us=value["expires_us"])
        except FileNotFoundError:
            return self.unavailable("PACKAGE_MISSING")
        except (OSError, ValueError, TypeError, KeyError, OverflowError,
                AttributeError, RuntimeError, subprocess.SubprocessError) as error:
            known = {"EXPIRED", "PUBLICATION_IN_PROGRESS", "PUBLICATION_CHANGED",
                "ROLLBACK_OR_CONFLICT", "CLOCK_REGRESSION", "UNSUPPORTED_SYMBOL"}
            return self.unavailable(str(error) if str(error) in known else "AUTHORITY_INVALID")

    def is_news_blocked(self, *, symbol, timestamp):
        return self.inspect(symbol=symbol, timestamp=timestamp)["blocked"]
