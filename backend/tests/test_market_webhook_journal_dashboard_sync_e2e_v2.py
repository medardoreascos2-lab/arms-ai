from datetime import datetime
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app


def build_signal() -> dict[str, object]:
    return {
        "approved": True,
        "status": "READY",
        "decision": "SEND_SIGNAL",
        "symbol": "NQ",
        "timeframe": "5M",
        "direction": "LONG",
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 110.0,
        "contracts": 2,
        "probability": 0.92,
        "confluence_score": 0.90,
        "grade": "A+",
        "blocking_reasons": [],
        "warnings": [],
        "summary": (
            "NQ LONG ENTRY 100.0 "
            "SL 95.0 TP 110.0"
        ),
    }


def build_webhook_payload() -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "1M",
        "open": 109.0,
        "high": 111.0,
        "low": 108.0,
        "close": 110.0,
        "volume": 1000.0,
        "timestamp": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "directional_momentum": 0.0,
        "adverse_structure": False,
    }


def test_webhook_close_syncs_journal_and_dashboard():
    app = create_app()
    client = TestClient(app)

    lifecycle = (
        app.state
        .trade_lifecycle_service_v2
    )

    journal = (
        app.state
        .trade_journal_v2
    )

    submitted = lifecycle.submit_signal(
        signal=build_signal(),
        order_type="MARKET",
        risk_context={
            "account_balance": 150000.0,
            "risk_percent": 0.5,
            "point_value": 20.0,
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
            "current_price": 100.0,
        },
        order_context={
            "market_is_open": True,
        },
    )

    assert submitted["accepted"] is True
    assert len(
        journal.get_open_trades()
    ) == 1

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json=build_webhook_payload(),
    )

    assert (
        response.status_code
        == 201
    ), response.text

    monitor_result = (
        response.json()[
            "price_feed"
        ][
            "monitor_result"
        ]
    )

    assert (
        monitor_result[
            "closed_positions"
        ]
        == 1
    )

    assert (
        journal.get_open_trades()
        == []
    )

    closed_trades = (
        journal.get_closed_trades()
    )

    assert len(closed_trades) == 1

    closed_trade = closed_trades[0]

    assert (
        closed_trade["status"]
        == "CLOSED"
    )

    assert (
        closed_trade["exit_reason"]
        == "TAKE_PROFIT"
    )

    assert (
        closed_trade["realized_pnl"]
        == 390.0
    )

    snapshot = (
        app.state
        .dashboard_live_data_service_v2
        .get_snapshot()
    )

    assert (
        snapshot[
            "dashboard_status"
        ]
        == "READY"
    )

    assert (
        snapshot[
            "trade_journal_summary"
        ][
            "open_trades"
        ]
        == 0
    )

    assert (
        snapshot[
            "trade_journal_summary"
        ][
            "closed_trades"
        ]
        == 1
    )

    assert (
        snapshot[
            "performance_overview"
        ][
            "total_trades"
        ]
        == 1
    )

    assert (
        snapshot[
            "performance_overview"
        ][
            "win_rate"
        ]
        == 100.0
    )

    assert (
        snapshot[
            "performance_overview"
        ][
            "net_profit"
        ]
        == 390.0
    )

    assert (
        snapshot[
            "account_overview"
        ][
            "balance"
        ]
        == 150390.0
    )
