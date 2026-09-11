from backend.api.app import create_app


def test_lifecycle_rejects_signal_with_explicit_blocking_reasons_even_if_other_a_plus_fields_are_valid():
    app = create_app()

    lifecycle = app.state.trade_lifecycle_service_v2

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
        "blocking_reasons": [
            "high_impact_news",
        ],
        "warnings": [],
        "summary": "NQ LONG explicit blocking reason authority probe",
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
    assert lifecycle.broker_connector_v2.get_orders() == []
    assert lifecycle.broker_connector_v2.get_fills() == []
    assert lifecycle.broker_connector_v2.get_positions() == []
    assert lifecycle.get_active_positions() == []
    assert lifecycle.protective_order_registry_v2.list_protections() == []
    assert lifecycle.oco_manager_v2.list_groups() == []
    assert lifecycle.portfolio_manager_v2.get_open_positions() == []
    assert lifecycle.trade_journal_v2.get_trades() == []
    assert result["prepared_order"] is None
    assert result["execution"] is None
    assert result["position"] is None
