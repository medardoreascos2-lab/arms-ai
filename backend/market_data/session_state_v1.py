"""Pure session/readiness projections over the existing certified calendar.

No provider lookup, timers, account access, orders or implicit holiday calendar.
REOPENING means this open interval has no admitted closed minute yet. PRE_OPEN
means before an explicitly supplied special-hours opening, not a guessed buffer.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, time, timedelta

from backend.market_data.current_candle_authority_v1 import CHICAGO, UTC, instant
from backend.services.certified_market_hours_runtime_provider_v2 import CertifiedMarketHoursRuntimeProviderV2
from backend.services.market_hours_service_v2 import MarketHoursServiceV2


@dataclass(frozen=True)
class SessionStateV1:
    state: str
    scheduled_open: bool = False
    segment_start: datetime | None = None
    reason: str = "CALENDAR_UNCERTIFIED"

    def snapshot(self):
        result = asdict(self)
        result["segment_start"] = self.segment_start.isoformat() if self.segment_start else None
        return result


class SessionStateAuthorityV1:
    def __init__(self, market_hours):
        if type(market_hours) is not CertifiedMarketHoursRuntimeProviderV2:
            raise TypeError("certified market hours required")
        self.hours = market_hours

    def _wall(self, day, value):
        naive = datetime.combine(day, value)
        candidates = [naive.replace(tzinfo=CHICAGO, fold=i) for i in (0, 1)]
        valid = {t.astimezone(UTC) for t in candidates
                 if t.astimezone(UTC).astimezone(CHICAGO).replace(tzinfo=None) == naive}
        if len(valid) != 1:
            raise ValueError("uncertain special-hours DST boundary")
        return valid.pop()

    def _intervals(self, day):
        calendar = self.hours.calendar_snapshot
        if calendar is None or day not in calendar.covered_dates:
            return None
        if day in calendar.closed_dates or day.weekday() == 5:
            return []
        midnight = self._wall(day, time())
        end = self._wall(day + timedelta(days=1), time())
        intervals = []
        if day.weekday() != 6:
            intervals.append((midnight, self._wall(day, MarketHoursServiceV2.DAILY_BREAK_START)))
        if day.weekday() != 4:
            intervals.append((self._wall(day, MarketHoursServiceV2.DAILY_BREAK_END), end))
        special = self.hours.special_hours_snapshot
        window = next((w for w in special.windows if w.local_date == day), None) if special else None
        if window:
            start, stop = self._wall(day, window.open_time), self._wall(day, window.close_time)
            intervals = [(max(a, start), min(b, stop)) for a, b in intervals if max(a, start) < min(b, stop)]
        return intervals

    def resolve(self, now, *, last_closed=None):
        try:
            now = instant(now)
            local = now.astimezone(CHICAGO)
            day = local.date()
            intervals = self._intervals(day)
            if intervals is None:
                return SessionStateV1("UNKNOWN")
            canonical_open = self.hours.get_market_hours_service().is_market_open(symbol="NQ", timestamp=now)
            if canonical_open != any(start <= now < end for start, end in intervals):
                return SessionStateV1("UNKNOWN", reason="CALENDAR_PROJECTION_MISMATCH")
            for start, end in intervals:
                if start <= now < end:
                    if start == self._wall(day, time()):
                        previous = self._intervals(day - timedelta(days=1))
                        if previous and previous[-1][1] == start:
                            start = previous[-1][0]
                    ready = last_closed is not None and start < instant(last_closed) <= now
                    return SessionStateV1("OPEN" if ready else "REOPENING", True, start,
                                          "FRESH_CLOSED_MINUTE" if ready else "AWAITING_CURRENT_SESSION_CLOSE")
            if day in self.hours.calendar_snapshot.closed_dates:
                state = "HOLIDAY_CLOSED"
            elif day.weekday() == 5 or (day.weekday() == 4 and local.time() >= MarketHoursServiceV2.WEEKLY_CLOSE) or (day.weekday() == 6 and local.time() < MarketHoursServiceV2.WEEKLY_OPEN):
                state = "WEEKEND_CLOSED"
            elif MarketHoursServiceV2.DAILY_BREAK_START <= local.time() < MarketHoursServiceV2.DAILY_BREAK_END:
                state = "DAILY_MAINTENANCE"
            else:
                special = self.hours.special_hours_snapshot
                window = next((w for w in special.windows if w.local_date == day), None) if special else None
                state = ("PRE_OPEN" if window and local.time() < window.open_time else
                         "EARLY_CLOSE" if window and window.close_time < MarketHoursServiceV2.DAILY_BREAK_START and local.time() >= window.close_time else
                         "SCHEDULED_CLOSED")
            return SessionStateV1(state, reason=state)
        except (ValueError, TypeError, OverflowError):
            return SessionStateV1("UNKNOWN", reason="TIME_OR_CALENDAR_INVALID")


def readiness_matrix(session, provider, *, fresh, recovery_clear, risk_ready=False, enabled=False):
    """Admission projection only. Never grants external execution authority.

    Market admission here is permission to validate an event, not acceptance.
    Existing price, chronology, calendar and freshness gates remain mandatory.
    """
    transport = provider == "CONNECTED"
    data = transport and session.scheduled_open is True and recovery_clear is True
    strategy = data and session.state == "OPEN" and fresh is True
    entries = strategy and risk_ready is True and enabled is True
    reason = ("RECOVERY_REQUIRED" if recovery_clear is not True else
              "PROVIDER_NOT_CONNECTED" if not transport else
              session.reason if not strategy else "DATA_READY")
    return dict(market_data_admission=data, strategy_admission=strategy, new_entry_admission=entries,
                position_management="CANONICAL_VALIDATED_CLOSES_ONLY" if data else "PRESERVE_STATE_NO_SYNTHETIC_FILL",
                readiness_status="DATA_READY" if strategy else "BLOCKED", reason_code=reason,
                sim_execution_authority="DISABLED", external_order_authority=False)
