"""Explicit provider-neutral closed-minute admission; never an order router."""
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from math import isfinite
from zoneinfo import ZoneInfo

from backend.models.candle import Candle
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.market_hours_service_v2 import MarketHoursServiceV2

UTC = timezone.utc
CHICAGO = ZoneInfo("America/Chicago")
MINUTE = timedelta(minutes=1)


def _stable(value):
    if hasattr(value, "__dataclass_fields__"):
        return _stable(asdict(value))
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _stable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_stable(v) for v in value)
    if isinstance(value, (tuple, list)):
        return [_stable(v) for v in value]
    return value


def instant(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("TIME_SYNC_INVALID")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class CurrentFeedContractV1:
    provider: str
    contract: str
    source_timezone: str
    bar_label: str
    trading_hours_template: str
    valid_from: datetime
    valid_until: datetime
    instrument: str = "NQ"
    tick_size: float = .25
    point_value: float = 20.0
    fixture: bool = False

    def __post_init__(self):
        if (not all(isinstance(v, str) and v.strip() for v in
                    (self.provider, self.contract, self.trading_hours_template))
                or self.instrument != "NQ" or self.tick_size != .25 or self.point_value != 20
                or self.bar_label not in {"OPEN", "CLOSE"} or type(self.fixture) is not bool
                or instant(self.valid_from) >= instant(self.valid_until)):
            raise ValueError("explicit NQ provider/contract/time specification required")
        ZoneInfo(self.source_timezone)


@dataclass(frozen=True)
class CurrentMarketEventV1:
    provider: str
    instrument: str
    contract: str
    kind: str
    event_time: datetime
    received_at: datetime
    bar_time: datetime
    sequence: int
    event_id: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timeframe: str = "1m"
    quality_flags: tuple = ()

    def fingerprint(self):
        payload = asdict(self)
        payload.pop("received_at")  # Transport retransmission is not a new event.
        for key in ("event_time", "bar_time"):
            payload[key] = instant(payload[key]).isoformat()
        return sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CurrentClosedObservationV1:
    provider: str
    contract: str
    canonical_timestamp: datetime
    available_at: datetime
    event_time: datetime
    received_at: datetime
    source_row: int
    event_id: str
    source_sha256: str
    calendar_sha256: str
    source_file: str
    raw_row: str
    ohlcv: tuple
    trading_date: str
    quality_flags: tuple = ()
    strategy_context_eligible: bool = True
    execution_price_eligible: bool = True
    session_accounting_eligible: bool = True

    def candle(self):
        return Candle("NQ", "1m", *self.ohlcv, self.canonical_timestamp)


class CurrentCandleAuthorityV1:
    """One serialized caller owns this gate. No forming bar becomes a final bar.

    Contiguous event sequences are part of the provider adapter's contract.
    Any unprovable ordering/continuity latches recovery. Duplicate cache eviction
    can only cause a fail-closed rejection, never re-admission of an old bar.
    """
    def __init__(self, *, contract, market_hours, maximum_age_seconds, clock):
        if type(contract) is not CurrentFeedContractV1 or type(market_hours) is not CertifiedMarketHoursRuntimeProviderV2:
            raise TypeError("explicit feed contract and certified market-hours authority required")
        if (type(maximum_age_seconds) not in (int, float) or not isfinite(maximum_age_seconds)
                or maximum_age_seconds <= 0 or not callable(clock)):
            raise ValueError("positive freshness bound and clock required")
        self.contract, self.market_hours = contract, market_hours
        self.clock, self.maximum_age = clock, maximum_age_seconds
        calendar = market_hours.calendar_snapshot
        if calendar is None:
            raise ValueError("certified current calendar required")
        self.digest = sha256(json.dumps(_stable((contract, calendar, market_hours.special_hours_snapshot)),
                                      sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.connected = False
        self.reconnecting = False
        self.fault = None
        self.last_sequence = None
        self.last_event_time = None
        self.last_closed = None
        self.last_received = None
        self.last_status = "DISCONNECTED"
        self.version = self.closed_count = self.duplicate_count = 0
        self._seen = OrderedDict()

    def fail(self, reason):
        self.fault = reason
        self.last_status = reason
        self.version += 1
        raise ValueError(reason)

    def connection(self, connected):
        if type(connected) is not bool:
            self.fail("DISCONNECTED")
        if self.fault:
            raise RuntimeError("RECOVERY_REQUIRED")
        if connected and not self.connected:
            self.reconnecting = self.last_sequence is not None
        self.connected = connected
        self.last_status = "CONTINUITY_PENDING" if self.reconnecting else "CONNECTED" if connected else "DISCONNECTED"
        self.version += 1

    def reasons(self):
        reasons = []
        if self.fault:
            reasons.extend((self.fault, "RECOVERY_REQUIRED"))
        if not self.connected:
            reasons.append("DISCONNECTED")
        if self.reconnecting:
            reasons.append("CONTINUITY_PENDING")
        if self.last_closed is None:
            reasons.append("AWAITING_MARKET_DATA")
        else:
            age = self.age_seconds()
            if age is None or age < 0:
                reasons.append("TIME_SYNC_INVALID")
            elif age > self.maximum_age:
                reasons.append("STALE_DATA")
        return reasons

    def age_seconds(self):
        if self.last_closed is None:
            return None
        try:
            return (instant(self.clock()) - self.last_closed).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None

    def _open(self, timestamp):
        return self.market_hours.get_market_hours_service().is_market_open(symbol="NQ", timestamp=timestamp)

    def _gap_proven_closed(self, start, end):
        if end - start > timedelta(days=7):
            return False
        while start < end:
            local = start.astimezone(CHICAGO)
            if not self.market_hours.is_date_covered(target_date=local.date()) or self._open(start):
                return False
            start += MINUTE
        return True

    def validate_segment(self, rows, *, contract):
        if contract != self.contract.contract or not rows:
            raise ValueError("UNKNOWN_CONTRACT")
        if any(type(r) is not CurrentClosedObservationV1 or r.contract != contract or r.calendar_sha256 != self.digest for r in rows):
            raise ValueError("only admitted current observations are allowed")

    def admit(self, event):
        if self.fault:
            raise RuntimeError("RECOVERY_REQUIRED")
        if not self.connected:
            raise RuntimeError("DISCONNECTED")
        if type(event) is not CurrentMarketEventV1:
            self.fail("INVALID_CANDLE")
        c = self.contract
        if (event.provider, event.instrument, event.contract) != (c.provider, c.instrument, c.contract):
            self.fail("UNKNOWN_CONTRACT")
        try:
            now, received, emitted, label = map(instant, (self.clock(), event.received_at, event.event_time, event.bar_time))
            fingerprint = event.fingerprint()
        except (ValueError, TypeError, OverflowError):
            self.fail("TIME_SYNC_INVALID")
        if type(event.sequence) is not int or event.sequence < 0 or not isinstance(event.event_id, str) or not event.event_id:
            self.fail("OUT_OF_ORDER")
        key = (event.sequence, event.event_id)
        if self._seen.get(key) == fingerprint:
            self.duplicate_count += 1
            self.last_status = "DUPLICATE"
            return None
        if self.last_sequence is not None and event.sequence != self.last_sequence + 1:
            self.fail("OUT_OF_ORDER")
        if any(event.event_id == ident for _, ident in self._seen):
            self.fail("DUPLICATE_CONFLICT")
        if (not 0 <= (now-received).total_seconds() <= self.maximum_age
                or not 0 <= (received-emitted).total_seconds() <= self.maximum_age
                or (self.last_event_time is not None and emitted < self.last_event_time)
                or event.bar_time.utcoffset() != event.bar_time.astimezone(ZoneInfo(c.source_timezone)).utcoffset()):
            self.fail("TIME_SYNC_INVALID")
        if event.kind not in {"RAW_EVENT", "FORMING_CANDLE", "CLOSED_CANONICAL_CANDLE"}:
            self.fail("INVALID_CANDLE")
        if event.timeframe != "1m" or event.quality_flags:
            self.fail("INVALID_CANDLE")
        self.last_sequence, self.last_event_time, self.last_received = event.sequence, emitted, received
        self._seen[key] = fingerprint
        if len(self._seen) > 2048:
            self._seen.popitem(last=False)
        self.version += 1
        self.last_status = event.kind
        if event.kind != "CLOSED_CANONICAL_CANDLE":
            return None
        start = label if c.bar_label == "OPEN" else label - MINUTE
        closed = start + MINUTE
        if start.second or start.microsecond or not closed <= emitted or not 0 <= (now-closed).total_seconds() <= self.maximum_age:
            self.fail("STALE_DATA" if closed < now else "TIME_SYNC_INVALID")
        if not instant(c.valid_from) <= start < closed <= instant(c.valid_until):
            self.fail("UNKNOWN_CONTRACT")
        try:
            prices = tuple(Decimal(str(x)) for x in (event.open, event.high, event.low, event.close))
            if (any(not x.is_finite() or x <= 0 or x % Decimal(".25") for x in prices)
                    or not prices[2] <= min(prices[0], prices[3]) <= max(prices[0], prices[3]) <= prices[1]
                    or type(event.volume) is not int or event.volume < 0):
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            self.fail("INVALID_CANDLE")
        if self.last_closed is not None:
            if start < self.last_closed:
                self.fail("OUT_OF_ORDER")
            if start > self.last_closed and not self._gap_proven_closed(self.last_closed, start):
                self.fail("RECOVERY_REQUIRED")
        if not self._open(start) or not self._open(closed-timedelta(microseconds=1)):
            self.fail("MARKET_HOURS_UNCERTIFIED_OR_CLOSED")
        self.last_closed = closed
        self.reconnecting = False
        self.closed_count += 1
        canonical = datetime.fromisoformat(start.astimezone(CHICAGO).isoformat())
        return CurrentClosedObservationV1(c.provider, c.contract, canonical, closed, emitted, received,
            event.sequence, event.event_id, fingerprint, self.digest, c.provider+"/"+c.contract,
            fingerprint, tuple(float(x) for x in prices)+(event.volume,),
            MarketHoursServiceV2.trading_day_for(closed).isoformat())
