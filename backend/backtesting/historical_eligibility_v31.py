"""Opt-in, research-grade native NQ observation contract. No live wiring.

The retained observation stream and the executable candle view are deliberately
different objects. Calendar exclusion is not source deletion or price repair.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from backend.models.candle import Candle

UTC = timezone.utc
CHICAGO = ZoneInfo("America/Chicago")
MINUTE = timedelta(minutes=1)
REVIEWED_CONTRACTS = tuple("JUN22 SEP22 DEC22 MAR23 JUN23 SEP23 DEC23 MAR24 JUN24 SEP24 DEC24 MAR25 JUN25".split())


@dataclass(frozen=True)
class HistoricalObservation:
    source_file: str
    source_sha256: str
    source_row: int
    raw_row: str
    source_timestamp: str
    contract: str
    canonical_timestamp: datetime
    available_at: datetime
    ohlcv: tuple
    source_observation_valid: bool
    strategy_context_eligible: bool
    execution_price_eligible: bool
    session_accounting_eligible: bool
    trading_date: str | None
    anomaly_reasons: tuple[str, ...]
    calendar_sha256: str

    def candle(self):
        # An offset-aware Chicago representation retains fold identity even in
        # legacy consumers that compare datetimes directly (same-ZoneInfo
        # comparisons otherwise ignore fold). No wall-clock relocalization.
        stamp = datetime.fromisoformat(self.canonical_timestamp.isoformat())
        return Candle("NQ", "1m", *(float(x) for x in self.ohlcv[:4]), self.ohlcv[4], stamp)


class HistoricalEligibilityV31:
    """Reviewed 2022-JUN25 calendar, explicitly injected and hash identified.

    The three eligibility decisions are separate fields. Under this conservative
    policy they share the same session/lifecycle predicate. Unknown calendars,
    contracts, invalid source rows and incompatible eligibility fail closed.
    """
    def __init__(self, template):
        if template.get("timezone") != "Central Standard Time" or not re.fullmatch(r"[0-9a-fA-F]{64}", template.get("sha256", "")):
            raise ValueError("reviewed Chicago calendar with source digest required")
        days = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
        expected = [{"BeginDay": days[(i-1) % 7], "BeginTime": "1700", "EndDay": days[i],
                     "EndTime": "1600", "TradingDay": days[i]} for i in range(5)]
        if template.get("sessions") != expected:
            raise ValueError("unreviewed weekly sessions")
        self.digest = template["sha256"]
        self.full = {date.fromisoformat(str(k)): v for k, v in template["full"].items()}
        self.partial = {date.fromisoformat(str(k)): dict(v) for k, v in template["partial"].items()}
        if self.full.keys() & self.partial.keys():
            raise ValueError("overlapping calendar overrides")
        for override in self.partial.values():
            if override["type"] not in {"EARLY_CLOSE", "LATE_OPEN"}:
                raise ValueError("unknown holiday override")
            time(*divmod(int(override["clock"]), 100))

    def session_bounds(self, day):
        if not 2022 <= day.year <= 2025:
            raise ValueError("outside reviewed calendar years")
        if day.weekday() >= 5 or day in self.full:
            return None
        start = datetime.combine(day-timedelta(days=1), time(17), CHICAGO)
        end = datetime.combine(day, time(16), CHICAGO)
        override = self.partial.get(day)
        if override:
            boundary = datetime.combine(day, time(*divmod(int(override["clock"]), 100)), CHICAGO)
            if override["type"] == "EARLY_CLOSE":
                end = boundary
            else:
                start = boundary
        return (start, end) if start < end else None

    @staticmethod
    def termination(contract):
        if contract not in REVIEWED_CONTRACTS:
            raise ValueError("outside reviewed contract lifecycle")
        month = {"MAR": 3, "JUN": 6, "SEP": 9, "DEC": 12}[contract[:3]]
        first = date(2000+int(contract[-2:]), month, 1)
        return datetime.combine(first+timedelta(days=(4-first.weekday()) % 7+14), time(8, 30), CHICAGO)

    def observation(self, raw, *, contract, source_file, source_sha256, source_row):
        fields = raw.split(";")
        if len(fields) != 6 or not re.fullmatch(r"\d{8} \d{6}", fields[0]):
            raise ValueError("native six-field minute schema required")
        end = datetime.strptime(fields[0], "%Y%m%d %H%M%S").replace(tzinfo=UTC)
        if end.second or source_row < 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", source_sha256):
            raise ValueError("invalid source lineage/minute")
        prices = tuple(Decimal(x) for x in fields[1:5])
        if not all(p.is_finite() and p > 0 and p % Decimal(".25") == 0 for p in prices):
            raise ValueError("invalid finite tick-aligned NQ price")
        o, h, low, c = prices
        if not low <= min(o, c) <= max(o, c) <= h or not re.fullmatch(r"\d+", fields[5]):
            raise ValueError("invalid OHLCV")
        opened = (end-MINUTE).astimezone(CHICAGO)
        day = opened.date() + (timedelta(days=1) if opened.hour >= 17 else timedelta())
        bounds = self.session_bounds(day)
        reasons = []
        if bounds is None or not (bounds[0].astimezone(UTC) <= end-MINUTE and end <= bounds[1].astimezone(UTC)):
            reasons.append("OUTSIDE_AUTHORIZED_SESSION")
        if end > self.termination(contract).astimezone(UTC):
            reasons.append("POST_CONTRACT_TERMINATION")
        eligible = not reasons
        return HistoricalObservation(str(source_file), source_sha256, source_row, raw, fields[0], contract,
            opened, end, (*prices, int(fields[5])), True, eligible, eligible, eligible,
            day.isoformat() if eligible else None, tuple(reasons), self.digest)

    def load_native(self, path, *, contract, expected_sha256):
        content = Path(path).read_bytes()
        if sha256(content).hexdigest() != expected_sha256.lower():
            raise ValueError("source hash mismatch")
        rows = tuple(self.observation(raw, contract=contract, source_file=str(path),
            source_sha256=expected_sha256, source_row=i)
            for i, raw in enumerate(content.decode("utf-8-sig").splitlines(), 1))
        self.validate_segment(rows, contract=contract)
        return rows

    def validate_segment(self, observations, *, contract):
        self.termination(contract)
        previous = None
        for row in observations:
            if row.contract != contract:
                raise ValueError("cross-contract prices forbidden")
            if previous is not None and row.available_at <= previous:
                raise ValueError("duplicate/backward source order")
            expected = self.observation(row.raw_row, contract=contract, source_file=row.source_file,
                source_sha256=row.source_sha256, source_row=row.source_row)
            if row != expected:
                raise ValueError("observation does not match authoritative eligibility policy")
            previous = row.available_at

    def eligible_candles(self, observations, *, contract):
        rows = tuple(observations)
        self.validate_segment(rows, contract=contract)
        return tuple(row.candle() for row in rows if row.strategy_context_eligible
                     and row.execution_price_eligible and row.session_accounting_eligible)

    def run_segment(self, engine, observations, *, contract):
        """Fresh single-contract composition; no ineligible marking or futures.

        Retain observations with the caller. END_OF_DATA remains a censored
        valuation: consumers must separate it from SL/TP completed outcomes.
        A terminal active lifecycle position is not force closed here.
        """
        candles = self.eligible_candles(observations, contract=contract)
        if not candles:
            raise ValueError("no eligible candles in segment")
        return engine.run_single_pass(candles)
