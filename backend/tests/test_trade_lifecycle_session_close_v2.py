from backend.tests.test_durable_crash_recovery_v2 import (
    build_runtime,
    open_position,
)


def test_session_close_synchronizes_full_paper_financial_state():
    lifecycle, account, store, recovery, startup = build_runtime()

    position = open_position(lifecycle)

    result = lifecycle.close_active_position(
        position_id=position["position_id"],
        current_price=105.0,
        reason="SESSION_CLOSE",
    )

    assert result["closed"] is True
    assert result["status"] == "CLOSED"

    closed = result["position"]

    assert closed["status"] == "CLOSED"
    assert closed["close_reason"] == "SESSION_CLOSE"
    assert closed["exit_price"] == 105.0
    assert closed["realized_pnl"] == 20.0
    assert closed["unrealized_pnl"] == 0.0

    assert lifecycle.get_active_positions() == []

    broker_positions = (
        lifecycle.broker_connector_v2.get_positions()
    )
    assert broker_positions
    assert all(
        item["status"] == "CLOSED"
        for item in broker_positions
    )

    portfolio = lifecycle.portfolio_manager_v2

    assert portfolio.get_open_positions() == []

    closed_positions = (
        portfolio.get_closed_positions()
    )
    assert len(closed_positions) == 1
    assert (
        portfolio.get_total_realized_pnl()
        == 20.0
    )

    assert account.get_state()["realized_pnl"] == 20.0

    assert len(
        lifecycle.trade_history_manager.get_history()
    ) == 1

    assert len(
        lifecycle.trade_journal_v2.trades
    ) == 1

    journal_trade = (
        lifecycle.trade_journal_v2.trades[0]
    )

    assert journal_trade.status == "CLOSED"
    assert journal_trade.pnl == 20.0

    assert not (
        store.protective_order_registry
        .list_protections(
            status="ACTIVE"
        )
    )

    assert not (
        store.oco_manager
        .list_groups(
            status="ACTIVE"
        )
    )
