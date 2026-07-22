from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.models.candle import Candle
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


def populate_store(
    store: LiveCandleStore,
    total: int = 60,
) -> None:
    start = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    for index in range(total):
        base = 21600.0 + index * 1.5

        store.add(
            Candle(
                symbol="NQ",
                timeframe="5m",
                open=base,
                high=base + 4.0,
                low=base - 2.0,
                close=base + 2.5,
                volume=1000.0 + index * 10,
                timestamp=(
                    start
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )


def test_analyzes_and_saves_latest_result():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["current_price"] == 21691.0
    assert "analyzed_at" in result

    saved = analysis_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert saved is not None
    assert saved["current_price"] == 21691.0
    assert saved["analyzed_at"] == result["analyzed_at"]


def test_uses_latest_requested_candles():
    candle_store = LiveCandleStore(
        max_candles=100
    )

    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=80,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    result = service.analyze(
        symbol="NQ",
        timeframe="5m",
        candle_limit=60,
        account_balance=17000.0,
        risk_percent=0.5,
        point_value=2.0,
        reward_risk_ratio=2.0,
    )

    assert result["current_price"] == 21721.0


def test_rejects_insufficient_candles():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=20,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    with pytest.raises(
        ValueError,
        match="velas",
    ):
        service.analyze(
            symbol="NQ",
            timeframe="5m",
            candle_limit=60,
            account_balance=17000.0,
            risk_percent=0.5,
            point_value=2.0,
            reward_risk_ratio=2.0,
        )


def test_can_analyze_when_minimum_is_reached():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=50,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    assert service.can_analyze(
        symbol="NQ",
        timeframe="5m",
        minimum_candles=50,
    ) is True


def test_cannot_analyze_before_minimum():
    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    populate_store(
        candle_store,
        total=49,
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    assert service.can_analyze(
        symbol="NQ",
        timeframe="5m",
        minimum_candles=50,
    ) is False
