from datetime import datetime, timezone

import pytest

from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


def build_journal() -> TradeJournalV2:
    return TradeJournalV2()


def build_open_trade(
    *,
    trade_id: str = "trade-001",
    position_id: str = "position-001",
    symbol: str = "NQ",
    direction: str = "LONG",
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "position_id": position_id,
        "symbol": symbol,
        "direction": direction,
        "entry_price": 100.0,
        "quantity": 2.0,
        "stop_loss": 90.0,
        "take_profit": 120.0,
        "entry_time": datetime(
            2026,
            7,
            25,
            13,
            0,
            tzinfo=timezone.utc,
        ),
        "status": "OPEN",
    }


def test_starts_empty():
    journal = build_journal()

    assert journal.get_open_trades() == []
    assert journal.get_closed_trades() == []

    summary = journal.get_summary()

    assert summary["open_trades"] == 0
    assert summary["closed_trades"] == 0
    assert summary["total_realized_pnl"] == 0.0


def test_records_open_trade():
    journal = build_journal()

    result = journal.record_open_trade(
        trade=build_open_trade(),
    )

    assert result["recorded"] is True
    assert result["status"] == "OPEN"
    assert result["trade_id"] == "trade-001"

    trade = journal.get_trade(
        trade_id="trade-001",
    )

    assert trade["symbol"] == "NQ"
    assert trade["direction"] == "LONG"


def test_rejects_duplicate_trade_id():
    journal = build_journal()

    trade = build_open_trade()

    journal.record_open_trade(
        trade=trade,
    )

    with pytest.raises(
        ValueError,
        match="trade_id",
    ):
        journal.record_open_trade(
            trade=trade,
        )


def test_updates_open_trade():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    result = journal.update_trade(
        trade_id="trade-001",
        updates={
            "stop_loss": 100.0,
            "take_profit": 130.0,
        },
    )

    assert result["updated"] is True
    assert result["trade"]["stop_loss"] == 100.0
    assert result["trade"]["take_profit"] == 130.0


def test_closes_long_trade():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    result = journal.close_trade(
        trade_id="trade-001",
        exit_price=110.0,
        exit_time=datetime(
            2026,
            7,
            25,
            13,
            5,
            tzinfo=timezone.utc,
        ),
        exit_reason="TAKE_PROFIT",
        point_value=2.0,
    )

    assert result["closed"] is True

    trade = result["trade"]

    assert trade["status"] == "CLOSED"
    assert trade["exit_price"] == 110.0
    assert trade["realized_pnl"] == 40.0
    assert trade["duration_seconds"] == 300.0
    assert trade["exit_reason"] == "TAKE_PROFIT"

    assert journal.get_open_trades() == []
    assert len(journal.get_closed_trades()) == 1


def test_closes_short_trade():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(
            trade_id="trade-short",
            direction="SHORT",
        ),
    )

    result = journal.close_trade(
        trade_id="trade-short",
        exit_price=90.0,
        exit_time=datetime(
            2026,
            7,
            25,
            13,
            10,
            tzinfo=timezone.utc,
        ),
        exit_reason="TAKE_PROFIT",
        point_value=2.0,
    )

    assert (
        result["trade"]["realized_pnl"]
        == 40.0
    )


def test_summary_after_closed_trades():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    journal.close_trade(
        trade_id="trade-001",
        exit_price=110.0,
        exit_time=datetime(
            2026,
            7,
            25,
            13,
            5,
            tzinfo=timezone.utc,
        ),
        exit_reason="TAKE_PROFIT",
        point_value=2.0,
    )

    summary = journal.get_summary()

    assert summary["open_trades"] == 0
    assert summary["closed_trades"] == 1
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 0
    assert summary["total_realized_pnl"] == 40.0
    assert summary["win_rate"] == 100.0


def test_getters_do_not_expose_internal_state():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    trades = journal.get_open_trades()

    trades[0]["symbol"] = "MODIFIED"

    fresh = journal.get_open_trades()

    assert fresh[0]["symbol"] == "NQ"


def test_rejects_invalid_trade_type():
    journal = build_journal()

    with pytest.raises(
        TypeError,
        match="trade",
    ):
        journal.record_open_trade(
            trade=object(),
        )


@pytest.mark.parametrize(
    "field",
    [
        "trade_id",
        "position_id",
        "symbol",
        "direction",
        "entry_price",
        "quantity",
        "entry_time",
    ],
)
def test_rejects_missing_required_fields(
    field,
):
    journal = build_journal()

    trade = build_open_trade()
    trade.pop(field)

    with pytest.raises(
        ValueError,
        match=field,
    ):
        journal.record_open_trade(
            trade=trade,
        )


def test_rejects_invalid_direction():
    journal = build_journal()

    trade = build_open_trade()
    trade["direction"] = "SIDEWAYS"

    with pytest.raises(
        ValueError,
        match="direction",
    ):
        journal.record_open_trade(
            trade=trade,
        )


def test_rejects_unknown_trade_update():
    journal = build_journal()

    with pytest.raises(
        KeyError,
        match="trade_id",
    ):
        journal.update_trade(
            trade_id="unknown",
            updates={
                "stop_loss": 100.0,
            },
        )


def test_rejects_unknown_trade_close():
    journal = build_journal()

    with pytest.raises(
        KeyError,
        match="trade_id",
    ):
        journal.close_trade(
            trade_id="unknown",
            exit_price=110.0,
            exit_time=datetime.now(
                timezone.utc
            ),
            exit_reason="MANUAL",
            point_value=2.0,
        )


def test_rejects_invalid_exit_price():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    with pytest.raises(
        ValueError,
        match="exit_price",
    ):
        journal.close_trade(
            trade_id="trade-001",
            exit_price=0.0,
            exit_time=datetime.now(
                timezone.utc
            ),
            exit_reason="MANUAL",
            point_value=2.0,
        )


def test_rejects_invalid_point_value():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    with pytest.raises(
        ValueError,
        match="point_value",
    ):
        journal.close_trade(
            trade_id="trade-001",
            exit_price=110.0,
            exit_time=datetime.now(
                timezone.utc
            ),
            exit_reason="MANUAL",
            point_value=0.0,
        )


def test_rejects_exit_before_entry():
    journal = build_journal()

    journal.record_open_trade(
        trade=build_open_trade(),
    )

    with pytest.raises(
        ValueError,
        match="exit_time",
    ):
        journal.close_trade(
            trade_id="trade-001",
            exit_price=110.0,
            exit_time=datetime(
                2026,
                7,
                25,
                12,
                59,
                tzinfo=timezone.utc,
            ),
            exit_reason="MANUAL",
            point_value=2.0,
        )
