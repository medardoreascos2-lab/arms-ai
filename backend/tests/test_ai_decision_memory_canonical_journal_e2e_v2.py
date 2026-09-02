from fastapi.testclient import TestClient

from backend.api.app import create_app


def _approved_signal():
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 20000.0,
        "stop_loss": 19990.0,
        "take_profit": 20020.0,
        "contracts": 1,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": "NQ LONG ENTRY 20000.0 SL 19990.0 TP 20020.0",
    }


def _risk_context():
    return {
        "account_balance": 150000.0,
        "risk_percent": 0.5,
        "point_value": 20.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
        "current_price": 20000.0,
    }


def test_ai_decision_memory_reads_canonical_closed_trade():
    app = create_app()

    lifecycle = app.state.trade_lifecycle_service_v2
    journal = app.state.trade_journal_v2
    monitor = app.state.live_position_monitor_v2

    journal.trades.clear()

    submitted = lifecycle.submit_signal(
        signal=_approved_signal(),
        order_type="MARKET",
        risk_context=_risk_context(),
        order_context={
            "market_is_open": True,
        },
    )

    assert submitted is not None

    positions = lifecycle.get_active_positions()

    assert len(positions) == 1

    closed_result = monitor.process_price(
        symbol="NQ",
        current_price=19990.0,
    )

    assert closed_result["processed"] is True
    assert closed_result["closed_positions"] == 1

    closed_trades = journal.get_closed_trades()

    assert len(closed_trades) == 1
    assert closed_trades[0].symbol == "NQ"
    assert closed_trades[0].direction == "LONG"
    assert closed_trades[0].status == "CLOSED"
    assert closed_trades[0].result == "STOP_LOSS"
    assert closed_trades[0].pnl == -205.0

    client = TestClient(app)

    response = client.get(
        "/api/v2/dashboard/ai-decision-memory"
    )

    assert response.status_code == 200

    payload = response.json()

    expected_keys = {
        "technical_confidence",
        "memory_confidence",
        "memory_adjustment",
        "final_confidence",
        "memory_reliability",
        "decision",
        "explanation",
        "recommendations",
    }

    assert set(payload.keys()) == expected_keys

    # One canonical losing trade must be visible to MemoryScoringEngine.
    #
    # For one loss:
    #   win_rate          = 0
    #   historical_score  = 0
    #   reliability       = LOW
    #   adjustment        = -5
    #
    # DecisionMemoryAdapter currently receives technical_confidence=93,
    # therefore final confidence must become 88.
    assert payload["technical_confidence"] == 93
    assert payload["memory_confidence"] == 0
    assert payload["memory_adjustment"] == -5
    assert payload["final_confidence"] == 88
    assert payload["memory_reliability"] == "LOW"
    assert payload["decision"] == "APPROVED"
