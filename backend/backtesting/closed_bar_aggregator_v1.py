"""V29R historical contract: Chicago open labels, completed inputs, full buckets."""

from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.models.candle import Candle


CHICAGO = ZoneInfo("America/Chicago")
MINUTE = timedelta(minutes=1)


def chicago_open(timestamp: datetime) -> datetime:
    """Interpret naive historical labels; reject ambiguous/nonexistent local times.

    Offset-aware input disambiguates the repeated DST hour. No source is mutated.
    """
    if timestamp.tzinfo is not None and timestamp.utcoffset() is not None:
        return timestamp.astimezone(CHICAGO)
    candidates = [timestamp.replace(tzinfo=CHICAGO, fold=fold) for fold in (0, 1)]
    valid = [t for t in candidates if t.astimezone(timezone.utc).astimezone(CHICAGO).replace(tzinfo=None) == timestamp]
    if not valid or (len(valid) == 2 and valid[0].utcoffset() != valid[1].utcoffset()):
        raise ValueError("Naive Chicago timestamp is ambiguous or nonexistent; supply an explicit offset")
    return valid[0]


class ClosedBarAggregatorV1:
    """Incrementally consume completed NQ 1m bars; emit complete 15m/1h bars.

    update_completed() is a completion notification, NOT an event at the open
    label. Each call advances availability to the input's open instant + 1m.
    No timers, calendar inference, filling or full-history resampling are used.
    """

    PERIODS = {"15m": 15, "1h": 60}

    def __init__(self, *, history_limit: int = 50):
        if history_limit <= 0:
            raise ValueError("history_limit must be positive")
        self._bars = {tf: deque(maxlen=history_limit) for tf in self.PERIODS}
        self._pending = {}
        self._last_instant = None
        self.available_at = None
        self.emitted_counts = dict.fromkeys(self.PERIODS, 0)

    def history(self, timeframe: str) -> list[Candle]:
        # Detached snapshots cannot mutate internal history or future snapshots.
        return [replace(bar) for bar in self._bars[timeframe]]

    def update_completed(self, candle: Candle) -> None:
        if candle.symbol.upper() != "NQ" or candle.timeframe.lower() != "1m":
            raise ValueError("Canonical historical aggregation requires NQ 1m candles")
        label = chicago_open(candle.timestamp)
        if label.second or label.microsecond:
            raise ValueError("1m open timestamp must lie on an exact minute")
        instant = label.astimezone(timezone.utc)
        if self._last_instant is not None and instant <= self._last_instant:
            raise ValueError("Completed candles must be strictly chronological and unique")
        self._last_instant = instant
        self.available_at = (instant + MINUTE).astimezone(CHICAGO)

        for timeframe, minutes in self.PERIODS.items():
            bucket = label.replace(minute=(label.minute // minutes) * minutes,
                                   second=0, microsecond=0)
            bucket_instant = bucket.astimezone(timezone.utc)
            slot = int((instant - bucket_instant) / MINUTE)
            pending = self._pending.get(timeframe)
            if pending is None or pending["bucket"] != bucket_instant:
                pending = {"bucket": bucket_instant, "count": 0,
                           "valid": slot == 0, "next": bucket_instant,
                           "bar": Candle("NQ", timeframe, candle.open, candle.high,
                                         candle.low, candle.close, 0, bucket)}
                self._pending[timeframe] = pending
            pending["valid"] = pending["valid"] and instant == pending["next"]
            pending["next"] = instant + MINUTE
            pending["count"] += 1
            bar = pending["bar"]
            bar.high = max(bar.high, candle.high)
            bar.low = min(bar.low, candle.low)
            bar.close = candle.close
            bar.volume += candle.volume
            if slot == minutes - 1:
                if pending["valid"] and pending["count"] == minutes:
                    self._bars[timeframe].append(bar)
                    self.emitted_counts[timeframe] += 1
                del self._pending[timeframe]
