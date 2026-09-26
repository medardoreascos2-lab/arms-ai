import json
import sqlite3

import pytest

from backend.backtesting.paper_session_close_service_v2 import (
    PaperSessionCloseServiceV2,
)
from backend.tests.test_operational_paper_sprint15 import (
    advance,
    make,
)
from backend.tests.test_paper_runtime_sprint08 import (
    fill_count,
    witness,
)


def test_flat_session_close_finishes_operational_paper_cleanly(
    tmp_path,
):
    op, clock = make(tmp_path)

    advance(op, clock, 0)
    witness(op.runtime)

    for index in range(1, 5):
        advance(op, clock, index)

    assert fill_count(op.runtime) == 1

    runtime = op.runtime._paper.runtime
    active = runtime.lifecycle.get_active_positions()

    assert len(active) == 1

    position = active[0]

    canonical_close = float(
        runtime.current.candle().close
    )

    prices_by_symbol = {
        str(position["symbol"]): canonical_close
    }

    service = PaperSessionCloseServiceV2(
        operational_paper=op,
    )

    report = service.close_session(
        prices_by_symbol=prices_by_symbol,
        policy="FLAT",
    )

    assert report["success"] is True
    assert report["status"] == "SESSION_CLOSED"
    assert report["policy"] == "FLAT"
    assert report["closed_positions"] == 1
    assert report["remaining_positions"] == 0

    assert op.enabled is False
    assert op.stopped is True

    assert runtime.lifecycle.get_active_positions() == []
    assert runtime.portfolio.get_open_positions() == []

    assert not any(
        report["reconciliation"].values()
    )

    closed = runtime.completed[-1]

    assert closed["exit_trigger"] == "SESSION_CLOSE"
    assert (
        closed["trigger_price"]
        == prices_by_symbol[position["symbol"]]
    )

    sign = (
        1
        if position["direction"] == "LONG"
        else -1
    )

    expected_fill = (
        prices_by_symbol[position["symbol"]]
        - sign * runtime.costs.slippage_points
    )

    assert closed["executed_exit"] == expected_fill

    state_path = tmp_path / "operational.sqlite"

    with sqlite3.connect(state_path) as db:
        row = db.execute(
            "SELECT payload, digest "
            "FROM checkpoint WHERE id=1"
        ).fetchone()

    assert row is not None

    payload = json.loads(row[0])

    assert payload["paper_ready"] is False
    assert payload["execution_state"] == "FLAT"



def test_missing_price_fails_closed_without_closing_position(
    tmp_path,
):
    op, clock = make(tmp_path)

    advance(op, clock, 0)
    witness(op.runtime)

    for index in range(1, 5):
        advance(op, clock, index)

    runtime = op.runtime._paper.runtime
    lifecycle = runtime.lifecycle

    active_before = lifecycle.get_active_positions()
    assert len(active_before) == 1

    service = PaperSessionCloseServiceV2(
        operational_paper=op,
    )

    with pytest.raises(
        ValueError,
        match="missing session close price",
    ):
        service.close_session(
            prices_by_symbol={},
            policy="FLAT",
        )

    active_after = lifecycle.get_active_positions()

    assert len(active_after) == 1
    assert (
        active_after[0]["position_id"]
        == active_before[0]["position_id"]
    )

    assert runtime.completed == []
    assert op.enabled is False
    assert (
        op.fault
        == "SESSION_CLOSE_RECOVERY_REQUIRED"
    )
    assert (
        op.runtime._fault
        == "RECOVERY_REQUIRED"
    )

    op.close()


def test_reconciliation_failure_does_not_declare_session_closed(
    tmp_path,
    monkeypatch,
):
    op, clock = make(tmp_path)

    advance(op, clock, 0)
    witness(op.runtime)

    for index in range(1, 5):
        advance(op, clock, index)

    runtime = op.runtime._paper.runtime
    position = runtime.lifecycle.get_active_positions()[0]

    canonical_close = float(
        runtime.current.candle().close
    )

    monkeypatch.setattr(
        op,
        "reconcile",
        lambda: {
            "duplicate_execution": 0,
            "duplicate_pnl": 0,
            "account_drift": 1,
            "journal_mismatch": 0,
            "unexplained_differences": 1,
        },
    )

    service = PaperSessionCloseServiceV2(
        operational_paper=op,
    )

    with pytest.raises(
        RuntimeError,
        match="PAPER_RECONCILIATION_FAILED",
    ):
        service.close_session(
            prices_by_symbol={
                position["symbol"]: canonical_close,
            },
            policy="FLAT",
        )

    assert op.stopped is False
    assert op.enabled is False
    assert (
        op.fault
        == "SESSION_CLOSE_RECOVERY_REQUIRED"
    )
    assert (
        op.runtime._fault
        == "RECOVERY_REQUIRED"
    )

    op.close()


def test_second_session_close_is_idempotent_without_duplicate_pnl(
    tmp_path,
):
    op, clock = make(tmp_path)

    advance(op, clock, 0)
    witness(op.runtime)

    for index in range(1, 5):
        advance(op, clock, index)

    runtime = op.runtime._paper.runtime
    position = runtime.lifecycle.get_active_positions()[0]

    canonical_close = float(
        runtime.current.candle().close
    )

    service = PaperSessionCloseServiceV2(
        operational_paper=op,
    )

    first = service.close_session(
        prices_by_symbol={
            position["symbol"]: canonical_close,
        },
        policy="FLAT",
    )

    completed_count = len(runtime.completed)
    journal_count = len(runtime.journal.trades)
    realized_pnl = runtime.account.get_state()[
        "realized_pnl"
    ]

    second = service.close_session(
        prices_by_symbol={
            position["symbol"]: canonical_close,
        },
        policy="FLAT",
    )

    assert second == first

    assert len(runtime.completed) == completed_count
    assert len(runtime.journal.trades) == journal_count

    assert (
        runtime.account.get_state()["realized_pnl"]
        == realized_pnl
    )
    assert runtime.lifecycle.get_active_positions() == []
