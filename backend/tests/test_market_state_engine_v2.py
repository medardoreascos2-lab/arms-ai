from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from datetime import timezone

from backend.market_state.market_state_engine_v2 import (
    MarketState,
    MarketStateEngineV2,
)


def build_timestamp() -> datetime:
    return datetime(
        2026,
        7,
        27,
        20,
        0,
        tzinfo=timezone.utc,
    )


def test_starts_empty():
    engine = MarketStateEngineV2()

    assert engine.snapshot() == {}

    assert (
        engine.get(
            symbol="NQ",
            timeframe="1M",
        )
        is None
    )


def test_updates_and_reads_state():
    engine = MarketStateEngineV2()
    timestamp = build_timestamp()

    engine.update(
        symbol="NQ",
        timeframe="1M",
        price=23000.25,
        timestamp=timestamp,
    )

    state = engine.get(
        symbol="NQ",
        timeframe="1M",
    )

    assert isinstance(
        state,
        MarketState,
    )

    assert state.symbol == "NQ"
    assert state.timeframe == "1M"
    assert state.last_price == 23000.25
    assert state.timestamp == timestamp


def test_replaces_same_market_state():
    engine = MarketStateEngineV2()

    engine.update(
        symbol="NQ",
        timeframe="1M",
        price=23000.25,
        timestamp=build_timestamp(),
    )

    new_timestamp = datetime(
        2026,
        7,
        27,
        20,
        1,
        tzinfo=timezone.utc,
    )

    engine.update(
        symbol="NQ",
        timeframe="1M",
        price=23005.50,
        timestamp=new_timestamp,
    )

    state = engine.get(
        symbol="NQ",
        timeframe="1M",
    )

    assert state is not None
    assert state.last_price == 23005.50
    assert state.timestamp == new_timestamp
    assert len(engine.snapshot()) == 1


def test_separates_symbols_and_timeframes():
    engine = MarketStateEngineV2()
    timestamp = build_timestamp()

    engine.update(
        symbol="NQ",
        timeframe="1M",
        price=23000.0,
        timestamp=timestamp,
    )

    engine.update(
        symbol="NQ",
        timeframe="5M",
        price=23010.0,
        timestamp=timestamp,
    )

    engine.update(
        symbol="ES",
        timeframe="1M",
        price=6100.0,
        timestamp=timestamp,
    )

    snapshot = engine.snapshot()

    assert len(snapshot) == 3
    assert snapshot[("NQ", "1M")].last_price == 23000.0
    assert snapshot[("NQ", "5M")].last_price == 23010.0
    assert snapshot[("ES", "1M")].last_price == 6100.0


def test_snapshot_returns_new_dictionary():
    engine = MarketStateEngineV2()

    engine.update(
        symbol="NQ",
        timeframe="1M",
        price=23000.0,
        timestamp=build_timestamp(),
    )

    snapshot = engine.snapshot()
    snapshot.clear()

    assert len(engine.snapshot()) == 1


def test_supports_concurrent_updates():
    engine = MarketStateEngineV2()
    timestamp = build_timestamp()

    def update_price(
        price: float,
    ) -> None:
        engine.update(
            symbol="NQ",
            timeframe="1M",
            price=price,
            timestamp=timestamp,
        )

    prices = [
        float(price)
        for price in range(
            23000,
            23100,
        )
    ]

    with ThreadPoolExecutor(
        max_workers=8,
    ) as executor:
        list(
            executor.map(
                update_price,
                prices,
            )
        )

    snapshot = engine.snapshot()

    assert len(snapshot) == 1
    assert snapshot[
        ("NQ", "1M")
    ].last_price in prices
