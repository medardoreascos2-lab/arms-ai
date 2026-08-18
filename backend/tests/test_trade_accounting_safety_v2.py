from backend.execution.trade_execution_simulator_v2 import (
    TradeExecutionSimulatorV2,
)

from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


def test_open_simulated_trade_has_zero_realized_pnl():

    simulator = TradeExecutionSimulatorV2()

    trade = simulator.execute(
        symbol="MNQ",
        direction="BUY",
        entry=20000.0,
        stop_loss=19950.0,
        take_profit=20100.0,
        contracts=2,
        risk_amount=200.0,
        approved=True,
    )

    assert trade.status == "OPEN"
    assert trade.pnl == 0.0


def test_blocked_trade_has_zero_pnl():

    simulator = TradeExecutionSimulatorV2()

    trade = simulator.execute(
        symbol="NQ",
        direction="SELL",
        entry=20000.0,
        stop_loss=20050.0,
        take_profit=19900.0,
        contracts=1,
        risk_amount=100.0,
        approved=False,
    )

    assert trade.status == "BLOCKED"
    assert trade.pnl == 0.0


def test_journal_long_close_calculates_realized_pnl():

    journal = TradeJournalV2()

    journal.record_open_trade(
        {
            "trade_id": "LONG-1",
            "position_id": "POS-1",
            "symbol": "MNQ",
            "direction": "LONG",
            "entry_price": 20000.0,
            "stop_loss": 19950.0,
            "take_profit": 20100.0,
            "quantity": 2,
        }
    )

    trade = journal.close_trade(
        trade_id="LONG-1",
        exit_price=20050.0,
        exit_reason="MANUAL",
        point_value=2.0,
    )

    assert trade.status == "CLOSED"
    assert trade.pnl == 200.0


def test_journal_short_close_calculates_realized_pnl():

    journal = TradeJournalV2()

    journal.record_open_trade(
        {
            "trade_id": "SHORT-1",
            "position_id": "POS-2",
            "symbol": "MNQ",
            "direction": "SHORT",
            "entry_price": 20000.0,
            "stop_loss": 20050.0,
            "take_profit": 19900.0,
            "quantity": 2,
        }
    )

    trade = journal.close_trade(
        trade_id="SHORT-1",
        exit_price=19950.0,
        exit_reason="MANUAL",
        point_value=2.0,
    )

    assert trade.status == "CLOSED"
    assert trade.pnl == 200.0


def test_journal_entries_receive_independent_timestamps():

    journal = TradeJournalV2()

    first = journal.record(
        trade_id="T1",
        symbol="MNQ",
        direction="LONG",
        entry=100.0,
        stop_loss=90.0,
        take_profit=120.0,
        contracts=1,
        risk_amount=20.0,
        status="OPEN",
    )

    second = journal.record(
        trade_id="T2",
        symbol="MNQ",
        direction="LONG",
        entry=101.0,
        stop_loss=91.0,
        take_profit=121.0,
        contracts=1,
        risk_amount=20.0,
        status="OPEN",
    )

    assert first.created_at is not None
    assert second.created_at is not None

    assert first.created_at is not second.created_at
