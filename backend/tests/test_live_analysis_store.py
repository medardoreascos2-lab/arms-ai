from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)


def build_analysis(
    *,
    symbol: str = "NQ",
    timeframe: str = "5m",
    score: float = 87.0,
    timestamp: datetime | None = None,
) -> dict[str, object]:
    if timestamp is None:
        timestamp = datetime(
            2026,
            7,
            22,
            19,
            30,
            tzinfo=timezone.utc,
        )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": 21691.0,
        "trend": "ALCISTA",
        "decision": {
            "score": score,
            "grade": "A+",
            "action": "BUY",
            "approved": True,
        },
        "probability": {
            "value": 84.0,
            "confidence": "MUY ALTA",
            "approved": True,
        },
        "risk": {
            "approved": True,
            "contracts": 2,
        },
        "analyzed_at": timestamp,
    }


def test_stores_and_returns_latest_analysis():
    store = LiveAnalysisStore()

    analysis = build_analysis()

    store.save(analysis)

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert result is not None
    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["decision"]["score"] == 87.0


def test_replaces_previous_analysis_for_same_market():
    store = LiveAnalysisStore()

    first_time = datetime(
        2026,
        7,
        22,
        19,
        30,
        tzinfo=timezone.utc,
    )

    second_time = (
        first_time
        + timedelta(minutes=5)
    )

    store.save(
        build_analysis(
            score=75.0,
            timestamp=first_time,
        )
    )

    store.save(
        build_analysis(
            score=91.0,
            timestamp=second_time,
        )
    )

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert result is not None
    assert result["decision"]["score"] == 91.0
    assert result["analyzed_at"] == second_time


def test_keeps_markets_separated():
    store = LiveAnalysisStore()

    store.save(
        build_analysis(
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.save(
        build_analysis(
            symbol="ES",
            timeframe="1m",
            score=82.0,
        )
    )

    nq = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    es = store.get_latest(
        symbol="ES",
        timeframe="1m",
    )

    assert nq is not None
    assert es is not None
    assert nq["symbol"] == "NQ"
    assert es["symbol"] == "ES"
    assert es["decision"]["score"] == 82.0


def test_returns_none_for_missing_market():
    store = LiveAnalysisStore()

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert result is None


def test_returns_copy_of_analysis():
    store = LiveAnalysisStore()

    store.save(
        build_analysis()
    )

    first = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert first is not None

    first["trend"] = "MODIFICADA"

    second = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert second is not None
    assert second["trend"] == "ALCISTA"


def test_rejects_missing_required_field():
    store = LiveAnalysisStore()

    analysis = build_analysis()
    analysis.pop("symbol")

    with pytest.raises(
        KeyError,
        match="symbol",
    ):
        store.save(analysis)


def test_rejects_empty_market_values():
    store = LiveAnalysisStore()

    analysis = build_analysis()
    analysis["symbol"] = " "

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        store.save(analysis)


def test_clears_single_market():
    store = LiveAnalysisStore()

    store.save(
        build_analysis(
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.save(
        build_analysis(
            symbol="ES",
            timeframe="1m",
        )
    )

    store.clear(
        symbol="NQ",
        timeframe="5m",
    )

    assert (
        store.get_latest(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )

    assert (
        store.get_latest(
            symbol="ES",
            timeframe="1m",
        )
        is not None
    )
