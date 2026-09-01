from backend.api.app import create_app


class LearningSpy:
    def __init__(self):
        self.calls = []

    def process_closed_trade(
        self,
        **kwargs,
    ):
        self.calls.append(dict(kwargs))


def test_real_app_monitor_close_reaches_trade_learning():
    app = create_app()

    monitor = app.state.live_position_monitor_v2
    lifecycle = app.state.trade_lifecycle_service_v2

    learning_spy = LearningSpy()

    # Replace only the downstream learning dependency.
    # Lifecycle, execution, position, portfolio, journal,
    # and monitor remain the real create_app() wiring.
    monitor.trade_learning_service_v2 = learning_spy

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

    submitted = lifecycle.submit_signal(
        signal=signal,
        order_type="MARKET",
        risk_context=risk_context,
        order_context=order_context,
    )

    assert submitted["accepted"] is True
    assert submitted["position"] is not None

    active_positions = lifecycle.get_active_positions()

    assert len(active_positions) == 1

    position = active_positions[0]

    assert position["symbol"] == "NQ"
    assert position["direction"] == "LONG"

    result = monitor.process_price(
        symbol="NQ",
        current_price=19990.0,
    )

    assert result["processed"] is True
    assert result["closed_positions"] == 1

    assert len(learning_spy.calls) == 1

    learned = learning_spy.calls[0]

    assert learned["symbol"] == "NQ"
    assert learned["direction"] == "LONG"
    assert learned["contracts"] == 1
    executed_entry = position["entry_price"]

    assert executed_entry == submitted["position"]["entry_price"]
    assert learned["entry"] == executed_entry
    assert learned["exit_price"] == 19990.0

    expected_real_pnl = (
        (19990.0 - executed_entry)
        * 1
        * 20.0
    )

    assert learned["real_pnl"] == expected_real_pnl
    assert learned["trade_id"]
