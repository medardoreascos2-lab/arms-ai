"""F105D: internal journal ingestion reads closed PAPER records only."""

from datetime import datetime, timezone

from backend.financial.journal_ingestion import ingest_paper_journal
from backend.journal.trade_journal_v2 import TradeJournalEntry

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def entry(trade_id, status="CLOSED", exit_price=101.0, closed_at=NOW):
    return TradeJournalEntry(
        trade_id=trade_id, symbol="NQ", direction="LONG", entry=100.0,
        stop_loss=99.0, take_profit=102.0, contracts=1, risk_amount=20.0,
        status=status, result="WIN", pnl=20.0, reasoning=[],
        created_at=NOW, exit_price=exit_price, closed_at=closed_at,
    )


def test_ingestion_uses_existing_records_without_writing_or_inventing_fills():
    open_item = entry("open", status="OPEN", exit_price=0, closed_at=None)
    closed_item = entry("closed")
    missing_exit = entry("missing", exit_price=0)
    source = [open_item, closed_item, missing_exit]
    result = ingest_paper_journal(source, {"NQ": "CME:NQ:2026-12"})
    assert len(result.trades) == 1
    assert result.trades[0].asset_id == "CME:NQ:2026-12"
    assert result.trades[0].fees is None and result.trades[0].slippage is None
    assert {row[0] for row in result.skipped} == {"open", "missing"}
    assert len(source) == 3 and open_item.status == "OPEN"
    assert result.analysis_only


def test_unknown_symbol_and_naive_timestamp_are_skipped():
    result = ingest_paper_journal((entry("a"),), {})
    assert not result.trades and result.skipped[0][1] == "ASSET_ID_UNKNOWN"
    naive = entry("b")
    naive.created_at = naive.created_at.replace(tzinfo=None)
    result = ingest_paper_journal((naive,), {"NQ": "CME:NQ:2026-12"})
    assert not result.trades
    with_timezone = ingest_paper_journal((naive,), {"NQ": "CME:NQ:2026-12"},
                                         source_timezone=timezone.utc)
    assert len(with_timezone.trades) == 1
