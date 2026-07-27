import pytest

from backend.market_data.market_data_hub_v2 import (
    MarketDataHubV2,
)


class FakePriceFeedService:

    def __init__(
        self,
        *,
        fail=False,
    ):
        self.calls = []
        self.fail = fail

    def process_price(
        self,
        *,
        symbol,
        current_price,
        source,
    ):
        if self.fail:
            raise RuntimeError(
                "price feed failure"
            )

        self.calls.append(
            {
                "symbol": symbol,
                "current_price": current_price,
                "source": source,
            }
        )

        return {
            "processed": True,
            "symbol": symbol,
            "current_price": current_price,
            "source": source,
            "monitor_processed": True,
        }


def build_hub(
    *,
    price_feed_service=None,
    reject_duplicates=True,
):
    return MarketDataHubV2(
        price_feed_service_v2=(
            price_feed_service
        ),
        reject_duplicates=(
            reject_duplicates
        ),
    )


def test_accepts_none_price_feed_service():
    hub = build_hub()

    assert (
        hub.price_feed_service_v2
        is None
    )


def test_rejects_invalid_price_feed_service():
    with pytest.raises(
        TypeError,
        match="price_feed_service_v2",
    ):
        build_hub(
            price_feed_service=object(),
        )


def test_rejects_invalid_reject_duplicates():
    with pytest.raises(
        TypeError,
        match="reject_duplicates",
    ):
        MarketDataHubV2(
            price_feed_service_v2=None,
            reject_duplicates="yes",
        )


def test_starts_empty():
    hub = build_hub()

    state = hub.get_state()

    assert state["message_count"] == 0
    assert state["processed_count"] == 0
    assert state["duplicate_count"] == 0
    assert state["error_count"] == 0
    assert state["last_symbol"] is None
    assert state["last_price"] is None
    assert state["last_source"] is None
    assert state["last_received_at"] is None


def test_processes_market_price():
    price_feed = FakePriceFeedService()

    hub = build_hub(
        price_feed_service=price_feed,
    )

    result = hub.process_market_price(
        symbol="NQ",
        current_price=22000.25,
        source="TRADINGVIEW",
    )

    assert result["processed"] is True
    assert result["duplicate"] is False
    assert result["symbol"] == "NQ"
    assert result["current_price"] == 22000.25
    assert result["source"] == "TRADINGVIEW"
    assert result["received_at"] is not None

    assert len(price_feed.calls) == 1

    assert price_feed.calls[0] == {
        "symbol": "NQ",
        "current_price": 22000.25,
        "source": "TRADINGVIEW",
    }


def test_normalizes_market_data():
    price_feed = FakePriceFeedService()

    hub = build_hub(
        price_feed_service=price_feed,
    )

    result = hub.process_market_price(
        symbol=" nq ",
        current_price=22000.0,
        source=" tradingview ",
    )

    assert result["symbol"] == "NQ"
    assert result["source"] == "TRADINGVIEW"


def test_returns_false_without_price_feed_service():
    hub = build_hub()

    result = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    assert result["processed"] is False
    assert result["reason"] == "no_price_feed_service"
    assert result["duplicate"] is False


def test_rejects_duplicate_price():
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

    state = hub.get_state()

    assert state["message_count"] == 2
    assert state["processed_count"] == 1
    assert state["duplicate_count"] == 1


def test_allows_same_price_from_different_source():
    price_feed = FakePriceFeedService()

    hub = build_hub(
        price_feed_service=price_feed,
    )

    first = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    second = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="BROKER",
    )

    assert first["processed"] is True
    assert second["processed"] is True

    assert len(price_feed.calls) == 2


def test_allows_duplicate_when_disabled():
    price_feed = FakePriceFeedService()

    hub = build_hub(
        price_feed_service=price_feed,
        reject_duplicates=False,
    )

    first = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="REPLAY",
    )

    second = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="REPLAY",
    )

    assert first["processed"] is True
    assert second["processed"] is True
    assert len(price_feed.calls) == 2


def test_tracks_multiple_symbols():
    price_feed = FakePriceFeedService()

    hub = build_hub(
        price_feed_service=price_feed,
    )

    hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    hub.process_market_price(
        symbol="ES",
        current_price=5500.0,
        source="TRADINGVIEW",
    )

    state = hub.get_state()

    assert state["message_count"] == 2
    assert state["processed_count"] == 2
    assert state["last_symbol"] == "ES"
    assert state["last_price"] == 5500.0


def test_rejects_empty_symbol():
    hub = build_hub()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        hub.process_market_price(
            symbol="",
            current_price=22000.0,
            source="TRADINGVIEW",
        )


def test_rejects_invalid_price():
    hub = build_hub()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        hub.process_market_price(
            symbol="NQ",
            current_price=0,
            source="TRADINGVIEW",
        )


def test_rejects_empty_source():
    hub = build_hub()

    with pytest.raises(
        ValueError,
        match="source",
    ):
        hub.process_market_price(
            symbol="NQ",
            current_price=22000.0,
            source="",
        )


def test_price_feed_failure_is_recorded():
    hub = build_hub(
        price_feed_service=(
            FakePriceFeedService(
                fail=True,
            )
        ),
    )

    result = hub.process_market_price(
        symbol="NQ",
        current_price=22000.0,
        source="BROKER",
    )

    assert result["processed"] is False
    assert result["reason"] == "price_feed_error"
    assert result["feed_error"] is True

    state = hub.get_state()

    assert state["message_count"] == 1
    assert state["processed_count"] == 0
    assert state["error_count"] == 1


def test_state_is_a_copy():
    hub = build_hub()

    state = hub.get_state()
    state["message_count"] = 999

    fresh_state = hub.get_state()

    assert fresh_state["message_count"] == 0


class FakeMarketStateEngine:

    def __init__(self):
        self.calls = []

    def update(
        self,
        *,
        symbol,
        timeframe,
        price,
        timestamp,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "price": price,
                "timestamp": timestamp,
            }
        )


def test_updates_market_state_after_processing_price():
    from datetime import datetime
    from datetime import timezone

    price_feed = FakePriceFeedService()
    market_state = FakeMarketStateEngine()

    hub = MarketDataHubV2(
        price_feed_service_v2=price_feed,
        market_state_engine_v2=market_state,
    )

    timestamp = datetime(
        2026,
        7,
        27,
        20,
        30,
        tzinfo=timezone.utc,
    )

    result = hub.process_market_price(
        symbol=" nq ",
        current_price=23000.25,
        source=" tradingview ",
        timeframe=" 1m ",
        timestamp=timestamp,
    )

    assert result["processed"] is True

    assert (
        result["market_state_updated"]
        is True
    )

    assert (
        result["market_state_error"]
        is False
    )

    assert market_state.calls == [
        {
            "symbol": "NQ",
            "timeframe": "1M",
            "price": 23000.25,
            "timestamp": timestamp,
        }
    ]

