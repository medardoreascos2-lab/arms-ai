from datetime import datetime

from backend.backtesting.replay_market_data_bridge_v2 import (
    ReplayMarketDataBridgeV2,
)
from backend.models.candle import Candle


class FakeMarketDataHub:

    def __init__(self):
        self.calls = []

    def process_market_price(
        self,
        *,
        symbol,
        current_price,
        source,
        timeframe,
        timestamp,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "current_price": current_price,
                "source": source,
                "timeframe": timeframe,
                "timestamp": timestamp,
            }
        )

        return {
            "processed": True,
        }


def build_candle():
    return Candle(
        symbol="NQ",
        timeframe="1m",
        open=100,
        high=101,
        low=99,
        close=100.5,
        volume=1000,
        timestamp=datetime(2026, 1, 1, 12, 0),
    )


def test_sends_candle_to_market_data_hub():

    hub = FakeMarketDataHub()

    bridge = ReplayMarketDataBridgeV2(
        market_data_hub_v2=hub,
    )

    candle = build_candle()

    result = bridge.publish(
        candle,
    )

    assert result["processed"] is True

    assert len(hub.calls) == 1

    assert hub.calls[0] == {
        "symbol": "NQ",
        "current_price": 100.5,
        "source": "HISTORICAL_REPLAY",
        "timeframe": "1m",
        "timestamp": candle.timestamp,
    }


def test_rejects_invalid_candle():

    hub = FakeMarketDataHub()

    bridge = ReplayMarketDataBridgeV2(
        market_data_hub_v2=hub,
    )

    try:
        bridge.publish(object())
        assert False
    except TypeError:
        pass
