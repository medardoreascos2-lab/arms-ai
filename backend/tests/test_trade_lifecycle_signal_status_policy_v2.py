from backend.api.app import create_app


def test_lifecycle_rejects_non_ready_signal_even_if_other_a_plus_fields_are_valid():
    app = create_app()

    lifecycle = app.state.trade_lifecycle_service_v2

    signal = {
        "approved": True,
        "status": "BLOCKED",
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
        "summary": "NQ LONG status authority probe",
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

    result = lifecycle.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=risk_context,
        order_context=order_context,
    )

    assert result.get("accepted") is False
