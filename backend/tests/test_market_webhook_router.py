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

    client.app.state.runtime_quote_authority_v2.publish_quote(
        symbol="NQ",
        bid=21690.75,
        ask=21691.00,
        timestamp=datetime.now(timezone.utc),
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


def test_legacy_owner_rejected_before_webhook_monitors_open_position():
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
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
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


def test_legacy_owner_rejected_before_webhook_keeps_position_open_when_levels_not_reached():
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
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
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


def test_legacy_owner_rejected_before_webhook_executes_partial_take_profit():
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
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
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


def test_legacy_owner_rejected_before_webhook_includes_exit_decision_recommendation():
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
            "take_profit": 21791.0,
            "contracts": 1,
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 21700.0,
            "high": 21710.0,
            "low": 21700.0,
            "close": 21708.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                7,
                22,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
            "directional_momentum": 0.75,
            "adverse_structure": False,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


def test_legacy_owner_rejected_before_webhook_returns_exit_recommendation_without_closing():
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
            "take_profit": 21791.0,
            "contracts": 1,
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 21698.0,
            "high": 21699.0,
            "low": 21685.0,
            "close": 21696.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                7,
                22,
                10,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
            "directional_momentum": -0.70,
            "adverse_structure": True,
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0


def test_legacy_owner_rejected_before_market_webhook_nq_stop_close_uses_instrument_point_value():
    from datetime import (
        datetime,
        timezone,
    )

    from fastapi.testclient import TestClient

    from backend.api.app import create_app
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
            "entry_price": 20000.0,
            "stop_loss": 19990.0,
            "take_profit": 20020.0,
            "contracts": 1,
            "executed": True,
            "status": "SIMULATED",
            "mode": "SIMULATED",
            "executed_at": datetime(
                2026,
                1,
                1,
                12,
                0,
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

    before = position_manager.get_open_position(symbol="NQ", timeframe="5m")
    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "NQ",
            "timeframe": "5m",
            "open": 19990.0,
            "high": 19991.0,
            "low": 19989.0,
            "close": 19990.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                1,
                1,
                12,
                1,
                tzinfo=timezone.utc,
            ).isoformat(),
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "legacy_position_ownership_unavailable"
    assert position_manager.get_open_position(symbol="NQ", timeframe="5m") == before
    assert client.app.state.trade_history_store.get_history(symbol="NQ", timeframe="5m", limit=10) == []
    assert client.app.state.live_candle_store.count(symbol="NQ", timeframe="5m") == 0

def test_market_webhook_unsupported_symbol_preserves_manual_point_value_fallback():
    from datetime import (
        datetime,
        timezone,
    )

    from fastapi.testclient import TestClient

    from backend.api.app import create_app

    client = TestClient(
        create_app(),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": "development-secret",
        },
        json={
            "symbol": "UNKNOWN",
            "timeframe": "5m",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1000.0,
            "timestamp": datetime(
                2026,
                1,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ).isoformat(),
        },
    )

    # Compatibility contract:
    # before symbol-aware trade-management wiring,
    # unsupported symbols were not rejected here.
    #
    # RiskStage / LiveMarketAnalysisService already
    # preserve the manual point-value fallback contract
    # for unsupported instruments.
    assert response.status_code == 201
