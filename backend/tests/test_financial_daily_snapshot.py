"""F109A: unknown daily sections do not substitute demo values."""

from datetime import date, datetime, timezone

from backend.financial.daily_snapshot import DailyFinancialSnapshot, SectionState

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_empty_daily_snapshot_keeps_every_section_unknown():
    snapshot = DailyFinancialSnapshot(date(2026, 10, 4), NOW)
    for name in ("nq", "mnq", "portfolio", "stocks_watchlist", "crypto",
                 "risk", "events", "arbitrage_radar", "trading_coach_note"):
        assert getattr(snapshot, name).state is SectionState.UNKNOWN
    assert snapshot.nq is not snapshot.mnq or snapshot.nq.state is SectionState.UNKNOWN
    assert snapshot.analysis_only
