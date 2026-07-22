from datetime import (
    datetime,
    timezone,
)

from backend.api.schemas.market import (
    MarketWebhookRequest,
)


def test_accepts_tradingview_payload():
    payload = MarketWebhookRequest(
        symbol="NQ",
        timeframe="5m",
        open=21600.0,
        high=21605.0,
        low=21598.0,
        close=21603.0,
        volume=1500.0,
        timestamp=datetime(
            2026,
            7,
            22,
            19,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert payload.symbol == "NQ"
    assert payload.timeframe == "5m"
    assert payload.close == 21603.0


def test_normalizes_symbol_and_timeframe():
    payload = MarketWebhookRequest(
        symbol="  nq  ",
        timeframe=" 5m ",
        open=1,
        high=2,
        low=0,
        close=1.5,
        volume=10,
        timestamp=datetime.now(
            timezone.utc
        ),
    )

    assert payload.symbol == "NQ"
    assert payload.timeframe == "5m"


def test_rejects_empty_symbol():
    try:
        MarketWebhookRequest(
            symbol=" ",
            timeframe="5m",
            open=1,
            high=2,
            low=0,
            close=1,
            volume=1,
            timestamp=datetime.now(
                timezone.utc
            ),
        )
    except Exception:
        return

    raise AssertionError(
        "Debe rechazar símbolos vacíos."
    )
