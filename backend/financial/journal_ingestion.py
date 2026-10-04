"""Read-only ingestion of existing internal PAPER journal records."""

from dataclasses import dataclass
from datetime import datetime, tzinfo
from decimal import Decimal
from typing import Mapping, Sequence

from backend.journal.trade_journal_v2 import TradeJournalEntry
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin, TradeSide


@dataclass(frozen=True)
class JournalIngestion:
    trades: tuple[FinancialTradeRecord, ...]
    skipped: tuple[tuple[str, str], ...]
    analysis_only: bool = True


def _aware(value: datetime, source_timezone: tzinfo | None) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("journal timestamp missing")
    if value.tzinfo is None or value.utcoffset() is None:
        if source_timezone is None or source_timezone.utcoffset(value) is None:
            raise ValueError("naive journal timestamp requires explicit source timezone")
        return value.replace(tzinfo=source_timezone)
    return value


def ingest_paper_journal(
    entries: Sequence[TradeJournalEntry],
    asset_ids_by_symbol: Mapping[str, str],
    *,
    source_timezone: tzinfo | None = None,
) -> JournalIngestion:
    """Convert snapshots only. Never call journal record/close methods."""
    trades = []
    skipped = []
    seen = set()
    for entry in tuple(entries):
        if not isinstance(entry, TradeJournalEntry):
            raise TypeError("TradeJournalEntry is required")
        record_id = str(entry.trade_id)
        if record_id in seen:
            skipped.append((record_id, "DUPLICATE_TRADE_ID"))
            continue
        seen.add(record_id)
        if entry.status != "CLOSED":
            skipped.append((record_id, "NOT_CLOSED"))
            continue
        if entry.symbol not in asset_ids_by_symbol:
            skipped.append((record_id, "ASSET_ID_UNKNOWN"))
            continue
        if entry.direction.upper() not in ("LONG", "SHORT"):
            skipped.append((record_id, "DIRECTION_UNKNOWN"))
            continue
        try:
            if entry.exit_price is None or float(entry.exit_price) <= 0:
                raise ValueError("EXIT_PRICE_MISSING")
            opened = _aware(entry.created_at, source_timezone)
            closed = _aware(entry.closed_at, source_timezone)
            trade = FinancialTradeRecord(
                record_id=record_id,
                source="internal:trade_journal_v2",
                origin=TradeOrigin.PAPER_OBSERVED,
                asset_id=asset_ids_by_symbol[entry.symbol],
                side=TradeSide(entry.direction.upper()),
                entry_price=Decimal(str(entry.entry)),
                exit_price=Decimal(str(entry.exit_price)),
                size=Decimal(str(entry.contracts)),
                stop_price=Decimal(str(entry.stop_loss)) if entry.stop_loss and entry.stop_loss > 0 else None,
                target_price=Decimal(str(entry.take_profit)) if entry.take_profit and entry.take_profit > 0 else None,
                entry_at=opened,
                exit_at=closed,
                strategy=None,
                market_regime=None,
                decision_evidence=(),
                result_pnl=Decimal(str(entry.pnl)) if entry.pnl is not None else None,
                fees=None,
                slippage=None,
            )
        except (TypeError, ValueError, ArithmeticError) as exc:
            skipped.append((record_id, str(exc)))
            continue
        trades.append(trade)
    return JournalIngestion(tuple(trades), tuple(skipped))
