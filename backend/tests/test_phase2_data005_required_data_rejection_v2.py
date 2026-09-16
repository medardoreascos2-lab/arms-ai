import pytest

from backend.tests.test_market_data_hub_v2 import (
    FakePriceFeedService,
    build_hub,
)


def test_data005_rejects_missing_symbol():
    hub = build_hub()

    with pytest.raises(ValueError, match="symbol"):
        hub.process_market_price(
            symbol="",
            current_price=22000.0,
            source="TRADINGVIEW",
        )


def test_data005_rejects_malformed_price():
    hub = build_hub()

    with pytest.raises((TypeError, ValueError)):
        hub.process_market_price(
            symbol="NQ",
            current_price="not-a-price",
            source="TRADINGVIEW",
        )


def test_data005_rejects_missing_source():
    hub = build_hub()

    with pytest.raises(ValueError, match="source"):
        hub.process_market_price(
            symbol="NQ",
            current_price=22000.0,
            source="",
        )


def test_data005_rejects_duplicate_required_data():
    price_feed = FakePriceFeedService()
    hub = build_hub(
        price_feed_service=price_feed,
        reject_duplicates=True,
    )

    first = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    second = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    assert first["processed"] is True
    assert second["processed"] is False
    assert second["duplicate"] is True
    assert second["reason"] == "duplicate_price"
    assert len(price_feed.calls) == 1


def test_data005_rejects_malformed_timestamp():
    hub = build_hub()

    with pytest.raises(TypeError, match="timestamp"):
        hub.process_market_price(
            symbol="NQ",
            current_price=22000.0,
            source="TRADINGVIEW",
            timestamp="not-a-datetime",
        )


def test_data005_rejects_conflicting_market_data_same_observation():
    from datetime import datetime, timezone

    price_feed = FakePriceFeedService()
    hub = build_hub(
        price_feed_service=price_feed,
        reject_duplicates=True,
    )

    observed_at = datetime(
        2026, 9, 15, 20, 0, 0,
        tzinfo=timezone.utc,
    )

    first = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
        timeframe="1M",
        timestamp=observed_at,
    )

    second = hub.process_market_price(
        symbol="NQ",
        current_price=22001.0,
        source="TRADINGVIEW",
        timeframe="1M",
        timestamp=observed_at,
    )

    assert first["processed"] is True
    assert second["processed"] is False
    assert second["duplicate"] is False
    assert second["reason"] == "conflicting_market_data"
    assert len(price_feed.calls) == 1
