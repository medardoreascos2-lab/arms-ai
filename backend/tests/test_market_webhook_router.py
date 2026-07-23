from datetime import (
    datetime,
    timezone,
)

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.services.live_candle_store import (
    LiveCandleStore,
)


def build_payload() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "open": 21600.0,
        "high": 21605.0,
        "low": 21598.0,
        "close": 21603.0,
        "volume": 1250.0,
        "timestamp": datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        ).isoformat(),
    }


def test_market_webhook_stores_candle():
    store = LiveCandleStore(
        max_candles=500
    )

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json=build_payload(),
    )

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "stored"
    assert body["symbol"] == "NQ"
    assert body["timeframe"] == "5m"
    assert body["count"] == 1

    candles = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(candles) == 1
    assert candles[0].close == 21603.0


def test_market_webhook_replaces_same_timestamp():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    first = build_payload()

    second = {
        **build_payload(),
        "close": 21604.5,
        "volume": 1400.0,
    }

    first_response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json=first,
    )

    second_response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json=second,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["count"] == 1

    candles = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(candles) == 1
    assert candles[0].close == 21604.5
    assert candles[0].volume == 1400.0


def test_market_webhook_rejects_invalid_ohlc():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["high"] = 21590.0

    response = client.post(
        "/market/webhook",
        json=payload,
    )

    assert response.status_code == 422


def test_market_webhook_rejects_negative_volume():
    store = LiveCandleStore()

    client = TestClient(
        create_app(
            live_candle_store=store
        )
    )

    payload = build_payload()
    payload["volume"] = -1

    response = client.post(
        "/market/webhook",
        json=payload,
    )

    assert response.status_code == 422


def build_candle_payload(
    index: int,
) -> dict[str, object]:
    from datetime import timedelta

    payload = build_payload()

    base = 21600.0 + index * 1.5
    start = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    payload.update(
        {
            "open": base,
            "high": base + 4.0,
            "low": base - 2.0,
            "close": base + 2.5,
            "volume": 1000.0 + index * 10,
            "timestamp": (
                start
                + timedelta(
                    minutes=index * 5
                )
            ).isoformat(),
        }
    )

    return payload


def test_market_webhook_auto_analyzes_at_minimum():
    from backend.services.live_analysis_store import (
        LiveAnalysisStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    client = TestClient(
        create_app(
            live_candle_store=candle_store,
            live_analysis_store=analysis_store,
        )
    )

    last_response = None

    for index in range(50):
        last_response = client.post(
            "/market/webhook",
            headers={
                "X-ARMS-TOKEN": "development-secret",
            },
            json=build_candle_payload(
                index
            ),
        )

    assert last_response is not None
    assert last_response.status_code == 201

    body = last_response.json()

    assert body["count"] == 50
    assert body["analysis_generated"] is True

    analysis = analysis_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert analysis is not None
    assert analysis["symbol"] == "NQ"
    assert analysis["timeframe"] == "5m"


def test_market_webhook_does_not_analyze_before_minimum():
    from backend.services.live_analysis_store import (
        LiveAnalysisStore,
    )

    candle_store = LiveCandleStore()
    analysis_store = LiveAnalysisStore()

    client = TestClient(
        create_app(
            live_candle_store=candle_store,
            live_analysis_store=analysis_store,
        )
    )

    response = None

    for index in range(49):
        response = client.post(
            "/market/webhook",
            headers={
                "X-ARMS-TOKEN": "development-secret",
            },
            json=build_candle_payload(
                index
            ),
        )

    assert response is not None
    assert response.status_code == 201
    assert (
        response.json()[
            "analysis_generated"
        ]
        is False
    )

    analysis = analysis_store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert analysis is None


def test_webhook_monitors_open_position():
    from datetime import (
        datetime,
        timezone,
    )

    from backend.execution.position_manager import (
        PositionManager,
    )
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    position_manager = PositionManager()
    trade_history_store = TradeHistoryStore()

    position_manager.open_position(
        {
            "symbol": "NQ",
            "timeframe": "5m",
            "action": "BUY",
            "entry_price": 21691.0,
            "stop_loss": 21672.25,
            "take_profit": 21728.50,
            "contracts": 2,
            "executed": True,
            "status": "SIMULATED",
            "mode": "SIMULATED",
            "executed_at": datetime(
                2026,
                7,
                22,
                9,
                30,
                tzinfo=timezone.utc,
            ),
        }
    )

    client = TestClient(
        create_app(
            position_manager=position_manager,
            trade_history_store=trade_history_store,
        )
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 21720.0,
            "high": 21731.0,
            "low": 21718.0,
            "close": 21730.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                7,
                22,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert "position_monitor" in body
    assert (
        body["position_monitor"]["status"]
        == "CLOSED"
    )
    assert (
        body["position_monitor"]["close_reason"]
        == "TAKE_PROFIT"
    )

    assert (
        position_manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )

    history = trade_history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(history) == 1


def test_webhook_keeps_position_open_when_levels_not_reached():
    from datetime import (
        datetime,
        timezone,
    )

    from backend.execution.position_manager import (
        PositionManager,
    )

    position_manager = PositionManager()

    position_manager.open_position(
        {
            "symbol": "NQ",
            "timeframe": "5m",
            "action": "BUY",
            "entry_price": 21691.0,
            "stop_loss": 21672.25,
            "take_profit": 21728.50,
            "contracts": 2,
            "executed": True,
            "status": "SIMULATED",
            "mode": "SIMULATED",
            "executed_at": datetime(
                2026,
                7,
                22,
                9,
                30,
                tzinfo=timezone.utc,
            ),
        }
    )

    client = TestClient(
        create_app(
            position_manager=position_manager
        )
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 21700.0,
            "high": 21705.0,
            "low": 21695.0,
            "close": 21700.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                7,
                22,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert "position_monitor" in body
    assert (
        body["position_monitor"]["status"]
        == "OPEN"
    )

    assert (
        position_manager.get_open_position(
            symbol="NQ",
            timeframe="5m",
        )
        is not None
    )


def test_webhook_executes_partial_take_profit():
    from datetime import (
        datetime,
        timezone,
    )

    from backend.execution.position_manager import (
        PositionManager,
    )
    from backend.services.trade_history_store import (
        TradeHistoryStore,
    )

    position_manager = PositionManager()
    trade_history_store = TradeHistoryStore()

    position_manager.open_position(
        {
            "symbol": "NQ",
            "timeframe": "5m",
            "action": "BUY",
            "entry_price": 21691.0,
            "stop_loss": 21672.25,
            "take_profit": 21791.0,
            "contracts": 2,
            "executed": True,
            "status": "SIMULATED",
            "mode": "SIMULATED",
            "executed_at": datetime(
                2026,
                7,
                22,
                9,
                30,
                tzinfo=timezone.utc,
            ),
        }
    )

    client = TestClient(
        create_app(
            position_manager=position_manager,
            trade_history_store=trade_history_store,
        )
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 21715.0,
            "high": 21725.0,
            "low": 21710.0,
            "close": 21721.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                7,
                22,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
        },
    )

    assert response.status_code == 201

    body = response.json()

    management = body["position_monitor"]

    assert (
        management["partial_take_profit"][
            "executed"
        ]
        is True
    )
    assert (
        management["partial_take_profit"][
            "contracts_closed"
        ]
        == 1
    )
    assert (
        management["partial_take_profit"][
            "contracts_remaining"
        ]
        == 1
    )
    assert (
        management["partial_take_profit"][
            "realized_pnl"
        ]
        == 60.0
    )

    position = position_manager.get_open_position(
        symbol="NQ",
        timeframe="5m",
    )

    assert position is not None
    assert position["contracts"] == 1

    history = trade_history_store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert history == []
