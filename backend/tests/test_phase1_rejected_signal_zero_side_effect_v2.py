from __future__ import annotations

import pytest

from backend.api.app import create_app


@pytest.fixture
def app():
    return create_app()


def _snapshot(lifecycle):
    broker = lifecycle.broker_connector_v2
    portfolio = lifecycle.portfolio_manager_v2
    journal = lifecycle.trade_journal_v2

    return {
        "active_positions": list(
            lifecycle.get_active_positions()
        ),
        "portfolio_positions": list(
            portfolio.get_open_positions()
        ),
        "orders": list(
            broker.get_orders()
        ),
        "fills": list(
            broker.get_fills()
        ),
        "journal": journal.get_summary(),
    }


def test_rejected_signal_has_zero_financial_side_effects(app):
    lifecycle = app.state.trade_lifecycle_service_v2

    before = _snapshot(lifecycle)

    result = lifecycle.submit_signal(
        signal={
            "symbol": "NQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "take_profit": 20100.0,
            "approved": False,
        },
        order_type="MARKET",
        risk_context={
            "account_balance": 150000.0,
            "risk_percent": 0.5,
            "point_value": 20.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 20000.0,
        },
    )

    assert result["accepted"] is False

    after = _snapshot(lifecycle)

    assert after["active_positions"] == before["active_positions"]
    assert after["portfolio_positions"] == before["portfolio_positions"]
    assert after["orders"] == before["orders"]
    assert after["fills"] == before["fills"]
    assert after["journal"] == before["journal"]
