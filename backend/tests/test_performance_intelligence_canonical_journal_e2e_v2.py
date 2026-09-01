from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_performance_dashboard_reads_canonical_closed_trade():
    app = create_app()

    lifecycle = app.state.trade_lifecycle_service_v2
    monitor = app.state.live_position_monitor_v2
    journal = app.state.trade_journal_v2

    signal = {
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
        "summary": (
            "NQ LONG ENTRY 20000.0 "
            "SL 19990.0 TP 20020.0"
        ),
    }

    risk_context = {
        "account_balance": 150000.0,
        "risk_percent": 0.5,
        "point_value": 20.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
        "current_price": 20000.0,
    }

    order_context = {
        "market_is_open": True,
    }

    assert len(journal.get_closed_trades()) == 0

    submitted = lifecycle.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=risk_context,
        order_context=order_context,
    )

    assert submitted["accepted"] is True

    positions = lifecycle.get_active_positions()

    assert len(positions) == 1

    closed_result = monitor.process_price(
        symbol="NQ",
        current_price=19990.0,
    )

    assert closed_result["processed"] is True
    assert closed_result["closed_positions"] == 1

    canonical_closed = journal.get_closed_trades()

    assert len(canonical_closed) == 1

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/dashboard/performance-intelligence"
        )

    assert response.status_code == 200

    payload = response.json()

    print(
        "CANONICAL_CLOSED_COUNT=",
        len(canonical_closed),
    )

    print(
        "CANONICAL_CLOSED=",
        canonical_closed,
    )

    print(
        "PERFORMANCE_PAYLOAD=",
        payload,
    )

    assert payload["total_trades"] == len(
        canonical_closed
    )

    assert payload["total_trades"] == 1
