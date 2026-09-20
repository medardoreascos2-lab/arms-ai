"""Read-only comparison of reviewed native calendar metadata with static XML.

This is snapshot provenance, not a platform signature or continuous attestation.
No market events, account objects or order interfaces are accepted here.
"""
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
import json
import xml.etree.ElementTree as ET
from uuid import UUID
from zoneinfo import ZoneInfo

NATIVE_SHA256 = "c7d1d601d758ee98e2aa314384ef997f388d1c3e454d205e71dbfa9795f04cf8"
QUERIES = (
    "2026-09-21T20:45:00", "2026-09-21T21:00:00", "2026-09-21T22:00:00",
    "2026-09-25T21:00:00", "2026-09-27T22:00:00", "2026-10-30T21:00:00",
    "2026-11-02T22:00:00", "2026-11-25T23:00:00", "2026-11-26T18:00:00",
    "2026-11-26T23:00:00", "2026-11-27T18:15:00", "2026-12-24T18:15:00",
    "2026-12-25T12:00:00")
CHICAGO = ZoneInfo("America/Chicago")
UTC = timezone.utc
DAYS = ("Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday")


def _unique(pairs):
    result = {}
    for k,v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_EVIDENCE_KEY")
        result[k] = v
    return result


def _session(node):
    return dict(begin_day=node.findtext("BeginDay"),begin_time=int(node.findtext("BeginTime")),
        end_day=node.findtext("EndDay"),end_time=int(node.findtext("EndTime")),trading_day=node.findtext("TradingDay"))


def _wall(day, hhmm):
    value = datetime.combine(day,time(hhmm//100,hhmm%100))
    candidates = {value.replace(tzinfo=CHICAGO,fold=i).astimezone(UTC) for i in (0,1)}
    candidates = {x for x in candidates if x.astimezone(CHICAGO).replace(tzinfo=None)==value}
    if len(candidates)!=1:
        raise ValueError("AMBIGUOUS_CALENDAR_WALL_TIME")
    return candidates.pop()


def compare_loaded_calendar(evidence, template_bytes):
    """Semantic comparison, also usable by explicitly synthetic mutation tests."""
    t = ET.fromstring(template_bytes).find("TradingHours")
    e = evidence
    expected = dict(schema="arms.nt.calendar-evidence.v1",observation_only=True,
        contract="NQ DEC26",expiry_month="2026-12-01",instrument="NQ",tick_size=.25,point_value=20,
        bars_type="Minute",bars_value=1,application_timezone="UTC",template=t.findtext("Name"),
        template_version=int(t.findtext("Version")),template_timezone=t.findtext("TimeZone"),
        completion="COMPLETE_METADATA_ONLY",native_certification="PENDING_REVIEW")
    if any(type(e.get(k)) is not type(v) or e[k]!=v for k,v in expected.items()):
        raise ValueError("NATIVE_METADATA_MISMATCH")
    if str(UUID(e["session"])) != e["session"] or not e["event_time"].endswith("Z"):
        raise ValueError("NATIVE_CAPTURE_IDENTITY_INVALID")
    datetime.fromisoformat(e["event_time"])
    sessions = [_session(n) for n in t.find("Sessions")]
    full = sorted(n.findtext("Date")[:10] for n in t.find("HolidaysSerializable"))
    partial = {n.findtext("Date")[:10]:n for n in t.find("PartialHolidaysSerializable")}
    constraints = [dict(date=d,early_end=n.findtext("IsEarlyEnd")=="true",late_begin=n.findtext("IsLateBegin")=="true",
        constraint=_session(n.find("Constraint")),sessions=[_session(s) for s in n.find("Sessions")])
        for d,n in sorted(partial.items()) if d.startswith("2026-")]
    if e["sessions"]!=sessions or e["holiday_dates"]!=full or e["partial_holiday_dates"]!=sorted(partial) or e["partial_holidays_2026"]!=constraints:
        raise ValueError("LOADED_CALENDAR_DEFINITIONS_MISMATCH")
    if [s["query_configured_time"] for s in e["samples"]]!=list(QUERIES):
        raise ValueError("ITERATOR_SAMPLE_COVERAGE_MISMATCH")
    for sample in e["samples"]:
        if sample["includes_end"] is not True or sample["begin_kind"]!="Utc" or sample["end_kind"]!="Utc":
            raise ValueError("ITERATOR_TIME_SEMANTICS_UNPROVEN")
        if not sample["begin"].endswith("Z") or not sample["end"].endswith("Z"):
            raise ValueError("ITERATOR_UTC_REQUIRED")
        query = datetime.fromisoformat(sample["query_configured_time"]).replace(tzinfo=UTC)
        candidates = []
        for offset in range(-1,11):
            day = query.astimezone(CHICAGO).date()+timedelta(days=offset)
            if day.isoformat() in full:
                continue
            for session in sessions:
                if session["trading_day"] != DAYS[day.weekday()]:
                    continue
                start_day = day-timedelta(days=(day.weekday()-DAYS.index(session["begin_day"]))%7)
                start, stop = _wall(start_day,session["begin_time"]), _wall(day,session["end_time"])
                override = partial.get(day.isoformat())
                if override is not None:
                    constraint = _session(override.find("Constraint"))
                    if override.findtext("IsEarlyEnd")!="true" or override.findtext("IsLateBegin")!="false" or len(override.find("Sessions")) or constraint["end_day"]!=DAYS[day.weekday()]:
                        raise ValueError("UNSUPPORTED_NATIVE_EXCEPTION")
                    stop = _wall(day,constraint["end_time"])
                if stop>=query and start<stop:
                    candidates.append((start,stop,day.isoformat()))
        if not candidates:
            raise ValueError("NO_STATIC_ITERATOR_COUNTERPART")
        expected_sample = min(candidates)
        actual = (datetime.fromisoformat(sample["begin"]),datetime.fromisoformat(sample["end"]),sample["trading_day"])
        if actual!=expected_sample:
            raise ValueError("SESSION_ITERATOR_MISMATCH")
    return dict(status="LOADED_NATIVE_MATCH",weekly_sessions=len(sessions),iterator_samples=len(e["samples"]),
        full_holiday_dates=len(full),partial_holiday_dates=len(partial),partial_constraints_2026=len(constraints),
        ordinary_binding="PASS",holiday_runtime_admission="BLOCKED_UNSUPPORTED_CIVIL_DATE_PROJECTION",
        timestamp_semantics="OBSERVED_UTC_NOT_PC_LOCAL",spring_dst_native="NOT_SAMPLED",
        direct_loaded_xml_hash="NOT_EXPOSED",get_next_session_return_value="NOT_CAPTURED")


def verify_loaded_binding(raw, template_bytes):
    """Only this reviewed immutable native witness can clear the ordinary gate."""
    if len(raw)>100000 or not raw.endswith(b"\n") or len(raw.splitlines())!=1 or sha256(raw).hexdigest()!=NATIVE_SHA256:
        raise ValueError("NATIVE_CALENDAR_EVIDENCE_CHANGED_OR_UNREVIEWED")
    e = json.loads(raw,object_pairs_hook=_unique)
    result = compare_loaded_calendar(e,template_bytes)
    return dict(**result,native_sha256=NATIVE_SHA256,session=e["session"],capture_timestamp=e["event_time"])
