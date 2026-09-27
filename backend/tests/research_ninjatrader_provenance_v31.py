"""Sprint 03 read-only timestamp hypothesis audit, not a production ingestor.

The current template is evidence, not an archived export-time calendar. No
hypothesis, fit statistic or closed-hours placement certifies a source row.
"""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from backend.tests.research_source_certification_v31 import (
    CHICAGO, MINUTE, parse_row, standard_expiry, weekly_placement,
)

UTC = timezone.utc
ZONES = {"Eastern": ZoneInfo("America/New_York"), "Central": CHICAGO, "UTC": UTC}
DAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
OPEN = "WITHIN_NORMAL_WEEKLY_HOURS"


def possible_instants(label, zone):
    """Return zero/one/two UTC instants; never silently select a DST fold."""
    if label.tzinfo is not None or label.second or label.microsecond:
        raise ValueError("naive exact-minute source label required")
    candidates = {label.replace(tzinfo=zone, fold=f).astimezone(UTC) for f in (0, 1)}
    return sorted(t for t in candidates if t.astimezone(zone).replace(tzinfo=None) == label)


def canonical_hypothesis(label, zone, convention):
    """Analytical mapping only. Subtraction is elapsed UTC time, not wall time."""
    if convention not in ("open", "end"):
        raise ValueError("explicit open/end convention required")
    candidates = possible_instants(label, zone)
    if len(candidates) != 1:
        raise ValueError("nonexistent or ambiguous source label")
    stamp = candidates[0]
    opened = stamp - MINUTE if convention == "end" else stamp
    return opened.astimezone(CHICAGO), opened + MINUTE


def _clock(value):
    hour, minute = divmod(int(value), 100)
    return time(hour, minute)


def read_template(path):
    content = Path(path).read_bytes()
    node = ET.fromstring(content).find("TradingHours")
    if node is None or node.findtext("TimeZone") != "Central Standard Time":
        raise ValueError("reviewed Central template required")
    sessions = [{c.tag: c.text for c in s} for s in node.findall("Sessions/Session")]
    expected = [{"BeginDay": DAYS[(i-1) % 7], "BeginTime": "1700",
                 "EndDay": DAYS[i], "EndTime": "1600", "TradingDay": DAYS[i]} for i in range(5)]
    if sessions != expected:
        raise ValueError("unreviewed weekly session structure")
    full, partial = {}, {}
    for h in node.findall("HolidaysSerializable/Holiday"):
        day = date.fromisoformat(h.findtext("Date")[:10])
        if 2022 <= day.year <= 2025:
            if day in full:
                raise ValueError("duplicate full holiday")
            full[day] = h.findtext("Description")
    for h in node.findall("PartialHolidaysSerializable/PartialHoliday"):
        day = date.fromisoformat(h.findtext("Date")[:10])
        if not 2022 <= day.year <= 2025:
            continue
        constraint = {c.tag: c.text for c in h.find("Constraint")}
        early, late = h.findtext("IsEarlyEnd") == "true", h.findtext("IsLateBegin") == "true"
        if early == late or len(h.find("Sessions")) or constraint["TradingDay"] != DAYS[day.weekday()]:
            raise ValueError("unreviewed partial holiday type")
        edge = "End" if early else "Begin"
        if constraint[edge + "Day"] != DAYS[day.weekday()]:
            raise ValueError("unreviewed cross-day partial holiday")
        _clock(constraint[edge + "Time"])
        if day in partial or day in full:
            raise ValueError("overlapping holiday definitions")
        partial[day] = {"type": "EARLY_CLOSE" if early else "LATE_OPEN",
                        "clock": constraint[edge + "Time"], "description": h.findtext("Description")}
    return {"path": str(path), "sha256": sha256(content).hexdigest(),
            "name": node.findtext("Name"), "timezone": node.findtext("TimeZone"),
            "version": node.findtext("Version"), "sessions": sessions, "full": full, "partial": partial}


def session_bounds(trading_day, template):
    if trading_day.weekday() >= 5 or trading_day in template["full"]:
        return None
    start = datetime.combine(trading_day-timedelta(days=1), time(17), CHICAGO)
    end = datetime.combine(trading_day, time(16), CHICAGO)
    holiday = template["partial"].get(trading_day)
    if holiday:
        boundary = datetime.combine(trading_day, _clock(holiday["clock"]), CHICAGO)
        if holiday["type"] == "EARLY_CLOSE":
            end = boundary
        elif holiday["type"] == "LATE_OPEN":
            start = boundary
        else:
            raise ValueError("unknown holiday type")
    return (start, end) if start < end else None


def template_placement(local_open, template):
    weekly = weekly_placement(local_open)
    if weekly != OPEN:
        return weekly
    local = local_open.astimezone(CHICAGO)
    day = local.date() + (timedelta(days=1) if local.hour >= 17 else timedelta())
    if day in template["full"]:
        return "HOLIDAY_FULL_CLOSE"
    bounds = session_bounds(day, template)
    if bounds is None or not bounds[0] <= local < bounds[1]:
        return "HOLIDAY_" + template["partial"][day]["type"]
    return OPEN


def expected_open_minutes(first, last, expiry, template):
    """Expected template slots, not a claim that every minute must trade."""
    lo, hi = first.astimezone(UTC), min(last.astimezone(UTC)+MINUTE, expiry.astimezone(UTC))
    day = first.astimezone(CHICAGO).date()
    final = last.astimezone(CHICAGO).date()+timedelta(days=1)
    total = 0
    while day <= final:
        bounds = session_bounds(day, template)
        if bounds:
            start, end = max(lo, bounds[0].astimezone(UTC)), min(hi, bounds[1].astimezone(UTC))
            total += max(0, int((end-start).total_seconds() // 60))
        day += timedelta(days=1)
    return total


def analyze_file(record, template):
    path = Path(record["source_path"])
    content = path.read_bytes()
    digest = sha256(content).hexdigest()
    if digest != record["sha256_before"]:
        raise ValueError("source hash differs from Sprint 01")
    lines = content.decode("utf-8-sig").splitlines()
    rows = [parse_row(line) for line in lines]
    labels = [r[0] for r in rows]
    if not labels or any(b <= a for a, b in zip(labels, labels[1:])):
        raise ValueError("nonempty strictly increasing source required")
    expiry = standard_expiry(record["contract"])
    hypotheses, exceptions, additional = {}, [], []
    prior_exceptions = {e["line"]: e for e in record["exceptions"]}
    raw_gaps = Counter(int((b-a).total_seconds() // 60) for a, b in zip(labels, labels[1:]) if b-a > MINUTE)
    for zone_name, zone in ZONES.items():
        mapped = [possible_instants(label, zone) for label in labels]
        dst = Counter({"nonexistent": sum(not x for x in mapped), "ambiguous": sum(len(x) == 2 for x in mapped)})
        for convention in ("open", "end"):
            counts, placements, maintenance = Counter(), Counter(), Counter()
            previous = first = last = None
            offset_changes, holiday_counts = [], Counter()
            for number, (row, possibilities) in enumerate(zip(rows, mapped), 1):
                if len(possibilities) != 1:
                    previous = None
                    continue
                opened_utc = possibilities[0] - (MINUTE if convention == "end" else timedelta())
                local = opened_utc.astimezone(CHICAGO)
                first = first or local
                last = local
                place = template_placement(local, template)
                weekly = weekly_placement(local)
                placements[place] += 1
                counts["decoded_rows"] += 1
                counts["weekly_mismatch_rows"] += weekly != OPEN
                counts["template_mismatch_rows"] += place != OPEN
                counts["holiday_additional_mismatch_rows"] += place.startswith("HOLIDAY_")
                counts["post_termination_rows"] += local >= expiry
                counts["allowed_rows_before_termination"] += place == OPEN and local < expiry
                counts["sunday_1700_rows"] += local.weekday() == 6 and local.time() == time(17) and place == OPEN
                if place.startswith("HOLIDAY_"):
                    day = local.date() + (timedelta(days=1) if local.hour >= 17 else timedelta())
                    holiday_counts[day.isoformat()] += 1
                if previous:
                    prior_raw, prior_local = previous
                    if (local-prior_local == timedelta(minutes=61) and local.date() == prior_local.date()
                            and local.weekday() < 4 and prior_local.time() == time(15, 59) and local.time() == time(17)):
                        maintenance["CDT" if local.dst() else "CST"] += 1
                    if prior_local.utcoffset() != local.utcoffset():
                        offset_changes.append({"previous_raw": prior_raw.isoformat(), "next_raw": row[0].isoformat(),
                                               "previous_open": prior_local.isoformat(), "next_open": local.isoformat()})
                    counts["nonincreasing_canonical_steps"] += opened_utc <= prior_local.astimezone(UTC)
                previous = row[0], local
                if zone_name == "UTC" and convention == "end" and (number in prior_exceptions or place.startswith("HOLIDAY_")):
                    old = prior_exceptions.get(number)
                    if old and (old["raw_label"] != row[0].isoformat() or old["weekly_placement"] != weekly):
                        raise ValueError("prior exception identity/placement mismatch")
                    item = {"line": number, "source_row": lines[number-1], "raw_label": row[0].isoformat(),
                            "hypothetical_chicago_open": local.isoformat(), "template_placement": place,
                            "post_termination": local >= expiry, "flat": row[1] == row[2] == row[3] == row[4],
                            "category": "unexplained", "admitted": False,
                            "tags": ["contract lifecycle" if local >= expiry else "maintenance/session boundary"] if old else ["holiday/early close"],
                            "reason": "Location in a closed interval is not evidence of a valid trade or source-origin explanation."}
                    (exceptions if old else additional).append(item)
            if first is not None:
                expected = expected_open_minutes(first, last, expiry, template)
                counts["template_slots_before_termination"] = expected
                counts["unrepresented_open_minutes_before_termination"] = expected - counts["allowed_rows_before_termination"]
            hypotheses[zone_name + "_" + convention] = {
                "counts": dict(counts), "placement_counts": dict(placements), "dst_label_failures": dict(dst),
                "aligned_maintenance_gaps_by_season": dict(maintenance), "observed_offset_changes": offset_changes,
                "holiday_mismatches_by_trading_date": dict(holiday_counts),
                "first_open": first.isoformat() if first else None, "last_open": last.isoformat() if last else None,
            }
    if len(exceptions) != len(prior_exceptions):
        raise ValueError("not all prior exceptions revisited")
    if sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError("source mutated during analysis")
    return {"contract": record["contract"], "source_path": str(path), "sha256": digest, "rows": len(rows),
            "hypotheses": hypotheses, "raw_gap_step_histogram_minutes": dict(sorted(raw_gaps.items())),
            "gap_interpretation": "Unrepresented template-open minutes may be sparse/no-trade/provider absence; cause unproven. No filling.",
            "prior_exceptions": exceptions, "additional_UTC_end_holiday_exceptions": additional,
            "exception_classification": dict(Counter(e["category"] for e in exceptions)),
            "certification": "BLOCKED"}
