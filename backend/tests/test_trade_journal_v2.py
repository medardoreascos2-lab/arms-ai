
from backend.execution.trade_journal_v2 import (
    TradeJournalV2,
)



def test_trade_journal_adds_trade():


    journal = TradeJournalV2()


    result = journal.add_trade(

        {
            "trade_id": "TRD-001",
            "strategy_id": "STR-001",
            "direction": "BUY",
            "entry": 23500,
            "status": "OPEN",
        }

    )


    assert result["status"] == (
        "RECORDED"
    )


    assert (
        result["trade"]["trade_id"]
        ==
        "TRD-001"
    )



def test_trade_journal_lists_trades():


    journal = TradeJournalV2()


    journal.add_trade(

        {
            "trade_id": "TRD-001",
            "direction": "BUY",
            "status": "OPEN",
        }

    )


    trades = journal.get_trades()


    assert len(trades) == 1



def test_trade_journal_blocks_invalid_trade():


    journal = TradeJournalV2()


    result = journal.add_trade(
        None
    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_TRADE"
    )
