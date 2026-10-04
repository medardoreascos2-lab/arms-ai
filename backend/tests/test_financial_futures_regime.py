"""F107C: market regimes retain NQ/MNQ separation and missingness."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.financial.futures_regime import FuturesRegime, analyze_regime_performance
from backend.financial.futures_session import FuturesRoot, FuturesTradeContext, SessionSegment, SessionType, VolatilityLabel
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_regime_performance_tracks_observed_sample_and_unknowns():
    trade = FinancialTradeRecord(
        "synthetic:t1", "synthetic:journal", TradeOrigin.PAPER_OBSERVED,
        "CME:MNQ:2026-12", TradeSide.LONG, Decimal("100"), Decimal("101"),
        Decimal("1"), Decimal("99"), Decimal("102"), NOW, NOW + timedelta(minutes=1),
        "setup-a", "RANGE", (), Decimal("-2"), Decimal("0"), Decimal("0"),
    )
    context = FuturesTradeContext(
        trade, FuturesRoot.MNQ, SessionType.ETH, SessionSegment.OTHER, False,
        VolatilityLabel.LOW_VOL, "synthetic:classification", "synthetic:dataset", "USD",
    )
    report = analyze_regime_performance((context,))
    assert report.root is FuturesRoot.MNQ
    assert report.groups[FuturesRegime.RANGE].sample_size == 1
    assert report.groups[FuturesRegime.RANGE].expectancy_quote == Decimal("-2")
    assert report.unknown_regime_count == 0
    assert report.analysis_only
