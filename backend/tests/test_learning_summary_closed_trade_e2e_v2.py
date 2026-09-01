from fastapi.testclient import TestClient

from backend.api.app import create_app


def test_closed_trade_is_visible_in_public_learning_summary():
    app = create_app()

    lifecycle = app.state.trade_lifecycle_service_v2
    monitor = app.state.live_position_monitor_v2
    learning = app.state.trade_learning_service_v2

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

    before = learning.get_learning_report()

    assert before.total_trades == 0

    submitted = lifecycle.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=risk_context,
        order_context=order_context,
    )

    assert submitted["accepted"] is True

    positions = lifecycle.get_active_positions()

    assert len(positions) == 1

    position = positions[0]

    closed = monitor.process_price(
        symbol="NQ",
        current_price=19990.0,
    )

    assert closed["processed"] is True
    assert closed["closed_positions"] == 1

    canonical_report = learning.get_learning_report()

    assert canonical_report.total_trades == 1
    assert canonical_report.losing_trades == 1
    assert canonical_report.dominant_direction == "LONG"
    assert canonical_report.best_pattern == (
        "ARMS AI Decision Engine"
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v2/learning/summary"
        )

    assert response.status_code == 200

    public_report = response.json()

    assert public_report["total_trades"] == (
        canonical_report.total_trades
    )
    assert public_report["winning_trades"] == (
        canonical_report.winning_trades
    )
    assert public_report["losing_trades"] == (
        canonical_report.losing_trades
    )
    assert public_report["win_rate"] == (
        canonical_report.win_rate
    )
    assert public_report["dominant_direction"] == (
        canonical_report.dominant_direction
    )
    assert public_report["best_pattern"] == (
        canonical_report.best_pattern
    )
    assert public_report["recommendation"] == (
        canonical_report.recommendation
    )
    assert public_report["insights"] == (
        canonical_report.insights
    )
