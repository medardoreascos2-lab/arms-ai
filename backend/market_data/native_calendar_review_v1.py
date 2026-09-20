"""Narrow, hash-bound ordinary ETH capture specification. No guessed holidays.

This validates the local template file, not the template loaded in native Bars.
Native SessionIterator/loaded-template evidence remains a separate prerequisite.
"""
from datetime import date, datetime, time, timedelta
from hashlib import sha256
import xml.etree.ElementTree as ET

from backend.market_data.current_candle_authority_v1 import CHICAGO, instant

TEMPLATE = "CME US Index Futures ETH"
TEMPLATE_SHA256 = "370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620"


def validate_native_spec(spec, template_bytes, now):
    """Return reviewed ordinary dates; reject any unsupported holiday mapping."""
    now = instant(now)
    if sha256(template_bytes).hexdigest() != TEMPLATE_SHA256 or spec.get("calendar_evidence_sha256") != TEMPLATE_SHA256:
        raise ValueError("CALENDAR_IDENTITY_CHANGED")
    t = ET.fromstring(template_bytes).find("TradingHours")
    if t is None or t.findtext("Name") != TEMPLATE or t.findtext("TimeZone") != "Central Standard Time":
        raise ValueError("CALENDAR_METADATA_CHANGED")
    contract = spec["contract"]
    expected = dict(provider="Provider31", contract="NQ DEC26", instrument="NQ", source_timezone="UTC",
                    bar_label="CLOSE", trading_hours_template=TEMPLATE, tick_size=.25, point_value=20, fixture=False)
    if any(type(contract.get(k)) is not type(v) or contract[k] != v for k,v in expected.items()):
        raise ValueError("FEED_IDENTITY_CHANGED")
    if spec.get("provider_enum") != "Provider31" or spec.get("expiry") != "2026-12-01":
        raise ValueError("PROVIDER_OR_MONTH_IDENTITY_CHANGED")
    begin, end = (instant(datetime.fromisoformat(contract[k])) for k in ("valid_from","valid_until"))
    if begin.isoformat() != "2026-09-21T00:00:00+00:00" or end.isoformat() != "2026-09-28T00:00:00+00:00":
        raise ValueError("REVIEWED_CAPTURE_DATES_CHANGED")
    if not begin <= now < end or not timedelta(0) < end-begin <= timedelta(days=14):
        raise ValueError("CAPTURE_WINDOW_NOT_CURRENT_OR_BOUNDED")
    days = [date.fromisoformat(s) for s in spec["covered_dates"]]
    needed = []
    day = begin.astimezone(CHICAGO).date()-timedelta(days=1)
    last = end.astimezone(CHICAGO).date()+timedelta(days=1)
    while day <= last:
        needed.append(day)
        day += timedelta(days=1)
    if days != needed or spec.get("closed_dates") != [] or spec.get("special_hours") != []:
        raise ValueError("ORDINARY_CAPTURE_COVERAGE_MISMATCH")
    affected = set()
    for key in ("HolidaysSerializable","PartialHolidaysSerializable"):
        for row in t.find(key):
            trading_day = date.fromisoformat(row.findtext("Date")[:10])
            # A native override belongs to an overnight trading day. Quarantine
            # both civil dates plus the following day until iterator comparison.
            affected.update(trading_day+timedelta(days=i) for i in (-1,0,1))
    if affected.intersection(days):
        raise ValueError("NATIVE_EXCEPTION_MAPPING_REQUIRED")
    return dict(status="LOCAL_TEMPLATE_BOUND_ORDINARY_DATES_ONLY", template_sha256=TEMPLATE_SHA256,
                loaded_native_calendar="PENDING_NATIVE_BINDING", covered_dates=[d.isoformat() for d in days])


def ordinary_calendar_context(hours, now):
    """Calendar projection only; absence of a next covered boundary stays unknown."""
    from backend.market_data.session_state_v1 import SessionStateAuthorityV1
    now = instant(now)
    authority = SessionStateAuthorityV1(hours)
    state = authority.resolve(now)
    if state.state == "UNKNOWN":
        return dict(state="UNKNOWN", next_boundary=None, trading_date=None)
    boundaries = []
    for offset in range(8):
        intervals = authority._intervals(now.astimezone(CHICAGO).date()+timedelta(days=offset))
        if intervals is None:
            break
        # Midnight splits are a civil-date representation, not native EOD.
        for a,b in intervals:
            for value in (a,b):
                if value > now and value.astimezone(CHICAGO).time() != time():
                    boundaries.append(value)
    local = now.astimezone(CHICAGO)
    trading_day = (local.date()+timedelta(days=local.hour >= 17)).isoformat() if state.scheduled_open else None
    return dict(state="OPEN" if state.scheduled_open else state.state,
                next_boundary=min(boundaries).isoformat() if boundaries else None, trading_date=trading_day)
