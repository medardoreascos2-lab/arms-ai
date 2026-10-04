"""Data-only daily financial intelligence snapshot with explicit missing sections."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class SectionState(str, Enum):
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DailySection:
    state: SectionState
    source: str | None = None
    observed_at: datetime | None = None
    dataset_reference: str | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        if self.state is SectionState.UNKNOWN:
            if any(value is not None for value in (self.source, self.observed_at, self.dataset_reference, self.summary)):
                raise ValueError("unknown section cannot claim data")
        else:
            if not self.source or not self.dataset_reference or self.observed_at is None:
                raise ValueError("available or stale section requires provenance")
            if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
                raise ValueError("section time must be timezone-aware")


UNKNOWN_SECTION = DailySection(SectionState.UNKNOWN)


@dataclass(frozen=True)
class DailyFinancialSnapshot:
    day: date
    generated_at: datetime
    nq: DailySection = UNKNOWN_SECTION
    mnq: DailySection = UNKNOWN_SECTION
    portfolio: DailySection = UNKNOWN_SECTION
    stocks_watchlist: DailySection = UNKNOWN_SECTION
    crypto: DailySection = UNKNOWN_SECTION
    risk: DailySection = UNKNOWN_SECTION
    events: DailySection = UNKNOWN_SECTION
    arbitrage_radar: DailySection = UNKNOWN_SECTION
    trading_coach_note: DailySection = UNKNOWN_SECTION
    analysis_only: bool = True

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if not self.analysis_only:
            raise ValueError("daily snapshot cannot grant execution authority")
