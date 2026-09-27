"""Read-only Milestone A evidence; never an ingestion adapter or candle builder.

UTC/end is a hypothesis for these files until the provenance gates pass.
Normal-weekly-hours placement classifies exceptions, not their causal origin.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
from zoneinfo import ZoneInfo


CHICAGO = ZoneInfo("America/Chicago")
UTC = timezone.utc
MINUTE = timedelta(minutes=1)
REQUIRED_GATES = (
    "source_integrity", "schema_and_order", "native_export_file_linkage",
    "expiry_and_price_lineage", "timestamp_mapping_evidence",
    "hours_exception_disposition",
)
REVIEWED_CONTRACTS = tuple(
    "JUN22 SEP22 DEC22 MAR23 JUN23 SEP23 DEC23 MAR24 JUN24 SEP24 DEC24 MAR25 JUN25".split()
)


def certification_status(gates: dict) -> str:
    """Evidence fit alone cannot substitute for any missing documentary gate."""
    return "CERTIFIED" if all(gates.get(k) == "PASS" for k in REQUIRED_GATES) else "BLOCKED"


def parse_row(line: str):
    fields = line.rstrip("\r\n").split(";")
    if len(fields) != 6 or not re.fullmatch(r"\d{8} \d{6}", fields[0]):
        raise ValueError("native six-field minute schema required")
    label = datetime.strptime(fields[0], "%Y%m%d %H%M%S")
    if label.second:
        raise ValueError("off-minute timestamp")
    o, h, low, c = (Decimal(x) for x in fields[1:5])
    if not all(x.is_finite() and x > 0 and x % Decimal("0.25") == 0 for x in (o, h, low, c)):
        raise ValueError("invalid NQ price")
    if not low <= min(o, c) <= max(o, c) <= h:
        raise ValueError("invalid OHLC")
    volume = int(fields[5])
    if volume < 0:
        raise ValueError("negative volume")
    return label, o, h, low, c, volume


def hypothetical_open(raw_label: datetime) -> datetime:
    """Analysis only: do not pass this assumption into production ingestion."""
    if raw_label.tzinfo is not None:
        raise ValueError("expected original naive native-format label")
    return (raw_label.replace(tzinfo=UTC) - MINUTE).astimezone(CHICAGO)


def weekly_placement(open_time: datetime) -> str:
    if open_time.tzinfo is None:
        raise ValueError("an unambiguous instant is required")
    local = open_time.astimezone(CHICAGO)
    minute = local.hour * 60 + local.minute
    day = local.weekday()
    if day == 5:
        return "SATURDAY_CLOSED"
    if day == 6 and minute < 1020:
        return "SUNDAY_BEFORE_REOPEN"
    if day == 4 and minute >= 960:
        return "FRIDAY_AFTER_CLOSE"
    if day < 4 and 960 <= minute < 1020:
        return "WEEKDAY_MAINTENANCE"
    return "WITHIN_NORMAL_WEEKLY_HOURS"


def standard_expiry(contract: str) -> datetime:
    """Reviewed JUN22-JUN25 dates only; never extrapolate holiday adjustments."""
    if contract not in REVIEWED_CONTRACTS:
        raise ValueError("expiry outside reviewed JUN22-JUN25 scope")
    month = {"MAR": 3, "JUN": 6, "SEP": 9, "DEC": 12}[contract[:3]]
    first = date(2000 + int(contract[-2:]), month, 1)
    third_friday = first + timedelta(days=(4 - first.weekday()) % 7 + 14)
    return datetime.combine(third_friday, time(8, 30), CHICAGO)


def naive_dst_status(label: datetime) -> str:
    variants = {label.replace(tzinfo=CHICAGO, fold=f).astimezone(UTC) for f in (0, 1)}
    valid = {v for v in variants if v.astimezone(CHICAGO).replace(tzinfo=None) == label}
    return {0: "nonexistent", 1: "valid", 2: "ambiguous"}[len(valid)]


def analyze_source(path: Path, contract: str, expected_sha256: str) -> dict:
    content = path.read_bytes()
    digest = sha256(content).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError(f"source hash mismatch: {contract}")
    rows = []
    for line_number, line in enumerate(content.decode("utf-8-sig").splitlines(), 1):
        row = parse_row(line)
        if rows and row[0] <= rows[-1][0]:
            raise ValueError(f"duplicate/backward label: {contract}:{line_number}")
        rows.append(row)
    if not rows:
        raise ValueError("empty source")
    expiry = standard_expiry(contract)
    exceptions = []
    gap_minutes = Counter()
    maintenance = Counter()
    sunday_first = {}
    sunday_reopens = []
    dst = Counter()
    transitions = []
    previous = None
    for number, row in enumerate(rows, 1):
        raw = row[0]
        local = hypothetical_open(raw)
        placement = weekly_placement(local)
        if placement != "WITHIN_NORMAL_WEEKLY_HOURS":
            exceptions.append({
                "line": number, "raw_label": raw.isoformat(),
                "hypothetical_open_chicago": local.isoformat(),
                "weekly_placement": placement,
                "lifecycle_placement": "AFTER_STANDARD_TERMINATION" if local >= expiry else "BEFORE_STANDARD_TERMINATION",
                "flat": row[1] == row[2] == row[3] == row[4], "volume": row[5],
                "resolution": "UNEXPLAINED_SOURCE_OBSERVATION",
                "admitted": False,
                "holiday_or_early_close_explanation": "NOT_ESTABLISHED; a shorter session does not authorize a row outside normal weekly hours",
                "source_absence_explanation": "NOT_APPLICABLE_TO_A_PRESENT_ROW",
                "maintenance_explanation": "TIME_PLACEMENT_ONLY_NOT_A_VALIDATION" if placement == "WEEKDAY_MAINTENANCE" else "NOT_IN_WEEKDAY_MAINTENANCE",
                "contract_lifecycle_explanation": "POST_TERMINATION_CONFLICT_NOT_PERMISSION_TO_DROP" if local >= expiry else "EXPIRY_DOES_NOT_EXPLAIN_ROW",
            })
        if local.weekday() == 6:
            day = local.date().isoformat()
            if local.hour >= 16:
                sunday_first.setdefault(day, local.isoformat())
            if local.hour == 17 and local.minute == 0:
                sunday_reopens.append({"line": number, "raw_label": raw.isoformat(), "open_chicago": local.isoformat()})
        dst[naive_dst_status(raw)] += 1
        if previous:
            prior_raw, prior_local = previous
            minutes = int((raw - prior_raw).total_seconds() / 60)
            if minutes > 1:
                gap_minutes[minutes] += 1
            if (minutes == 61 and prior_local.weekday() < 4
                    and prior_local.date() == local.date()
                    and (prior_local.hour, prior_local.minute) == (15, 59)
                    and (local.hour, local.minute) == (17, 0)):
                maintenance["CDT" if local.dst() else "CST"] += 1
            if prior_local.utcoffset() != local.utcoffset():
                transitions.append({"previous_raw": prior_raw.isoformat(), "next_raw": raw.isoformat(),
                                    "previous_open_chicago": prior_local.isoformat(), "next_open_chicago": local.isoformat()})
        previous = raw, local
    after = sha256(path.read_bytes()).hexdigest()
    if after != digest:
        raise ValueError(f"source changed during analysis: {contract}")
    gates = {
        "source_integrity": "PASS", "schema_and_order": "PASS",
        "native_export_file_linkage": "UNRESOLVED",
        "expiry_and_price_lineage": "UNRESOLVED",
        "timestamp_mapping_evidence": "SUPPORTING_ONLY",
        "hours_exception_disposition": "UNRESOLVED" if exceptions else "NO_WEEKLY_EXCEPTIONS_NOT_FULL_CALENDAR_CERTIFICATION",
    }
    return {
        "contract": contract, "source_path": str(path), "sha256_before": digest, "sha256_after": after,
        "raw_rows": len(rows), "native_timestamp_format": "yyyyMMdd HHmmss; no offset or label convention embedded",
        "observed_first_raw": rows[0][0].isoformat(), "observed_last_raw": rows[-1][0].isoformat(),
        "proposed_source_timezone": "UTC", "proposed_label_semantics": "END_OF_BAR",
        "conversion": "attach UTC to raw end; subtract 60 elapsed seconds in UTC; convert to aware America/Chicago open; available_at=original UTC end",
        "hypothesis_only": True,
        "maintenance_evidence": {"aligned_61_minute_gaps": sum(maintenance.values()), "season_counts": dict(maintenance), "all_61_minute_gaps": gap_minutes[61]},
        "sunday_evidence": {"exact_1700_count": len(sunday_reopens), "exact_reopens": sunday_reopens, "first_observed_at_or_after_1600_by_date": sunday_first},
        "dst_evidence": {"naive_chicago_counterfactual": dict(dst), "UTC_end_observed_offset_transitions": transitions,
                         "note": "No transition inside a file is absence of test coverage, not proof; UTC itself has no local fold/gap."},
        "standard_termination_chicago": expiry.isoformat(),
        "observed_gap_evidence": {"nonconsecutive_steps": sum(gap_minutes.values()), "unrepresented_elapsed_minutes": sum((k-1)*v for k,v in gap_minutes.items()),
                                  "meaning": "Includes scheduled closures and possible sparse/absent source data; not a count of missing traded minutes."},
        "exception_count": len(exceptions), "exception_categories": dict(Counter(e["weekly_placement"] for e in exceptions)),
        "post_standard_termination_exceptions": sum(e["lifecycle_placement"] == "AFTER_STANDARD_TERMINATION" for e in exceptions),
        "exceptions": exceptions, "gates": gates, "certification_status": certification_status(gates),
        "confidence": "Documented native format and empirical consistency support UTC/end; neither establishes this file's exact export/transform history.",
    }
