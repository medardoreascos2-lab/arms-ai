import pytest

from backend.services.price_feed_service_v2 import (
    PriceFeedServiceV2,
)


class FakeLivePositionMonitor:

    def __init__(self):
        self.calls = []

    def process_price(
        self,
        *,
        symbol,
        current_price,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "current_price": current_price,
            }
        )

        return {
            "processed": True,
            "symbol": symbol,
            "current_price": current_price,
            "matched_positions": 1,
            "closed_positions": 0,
        }


def build_service(
    *,
    live_position_monitor=None,
):
    return PriceFeedServiceV2(
        live_position_monitor_v2=(
            live_position_monitor
        ),
    )


def test_accepts_none_monitor():
    service = build_service()

    assert (
        service.live_position_monitor_v2
        is None
    )


def test_rejects_invalid_monitor():
    with pytest.raises(
        TypeError,
        match="live_position_monitor_v2",
    ):
        build_service(
            live_position_monitor=object(),
        )


def test_starts_empty():
    service = build_service()

    state = service.get_state()

    assert state["price_count"] == 0
    assert state["last_symbol"] is None
    assert state["last_price"] is None
    assert state["last_source"] is None
    assert state["last_received_at"] is None
    assert state["monitor_calls"] == 0
    assert state["monitor_errors"] == 0


def test_processes_price():
    service = build_service()

    result = service.process_price(
        symbol="NQ",
        current_price=22000.25,
        source="TRADINGVIEW",
    )

    assert result["processed"] is True
    assert result["symbol"] == "NQ"
    assert result["current_price"] == 22000.25
    assert result["source"] == "TRADINGVIEW"
    assert result["received_at"] is not None
    assert result["monitor_processed"] is False
    assert result["monitor_result"] is None


def test_normalizes_symbol_and_source():
    service = build_service()

    result = service.process_price(
        symbol=" nq ",
        current_price=22000.0,
        source=" tradingview ",
    )

    assert result["symbol"] == "NQ"
    assert result["source"] == "TRADINGVIEW"


def test_forwards_price_to_monitor():
    monitor = FakeLivePositionMonitor()

    service = build_service(
        live_position_monitor=monitor,
    )

    result = service.process_price(
        symbol="NQ",
        current_price=22010.0,
        source="TRADINGVIEW",
    )

    assert result["monitor_processed"] is True

    assert len(monitor.calls) == 1

    assert monitor.calls[0] == {
        "symbol": "NQ",
        "current_price": 22010.0,
    }

    assert (
        result["monitor_result"][
            "matched_positions"
        ]
        == 1
    )


def test_tracks_multiple_prices():
    service = build_service(
        live_position_monitor=(
            FakeLivePositionMonitor()
        ),
    )

    service.process_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    service.process_price(
        symbol="NQ",
        current_price=22005.0,
        source="TRADINGVIEW",
    )

    state = service.get_state()

    assert state["price_count"] == 2
    assert state["last_symbol"] == "NQ"
    assert state["last_price"] == 22005.0
    assert state["last_source"] == "TRADINGVIEW"
    assert state["monitor_calls"] == 2


def test_rejects_empty_symbol():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        service.process_price(
            symbol="",
            current_price=22000.0,
            source="TRADINGVIEW",
        )


def test_rejects_invalid_price():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        service.process_price(
            symbol="NQ",
            current_price=0,
            source="TRADINGVIEW",
        )


def test_rejects_empty_source():
    service = build_service()

    with pytest.raises(
        ValueError,
        match="source",
    ):
        service.process_price(
            symbol="NQ",
            current_price=22000.0,
            source="",
        )


def test_monitor_failure_is_recorded():
    class FailingMonitor:

        def process_price(
            self,
            *,
            symbol,
            current_price,
        ):
            raise RuntimeError(
                "monitor failure"
            )

    service = build_service(
        live_position_monitor=(
            FailingMonitor()
        ),
    )

    result = service.process_price(
        symbol="NQ",
        current_price=22000.0,
        source="TRADINGVIEW",
    )

    assert result["processed"] is True
    assert result["monitor_processed"] is False
    assert result["monitor_error"] is True

    state = service.get_state()

    assert state["price_count"] == 1
    assert state["monitor_calls"] == 1
    assert state["monitor_errors"] == 1


def test_state_is_a_copy():
    service = build_service()

    state = service.get_state()
    state["price_count"] = 999

    fresh_state = service.get_state()

    assert fresh_state["price_count"] == 0
