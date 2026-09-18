"""Focused Phase 1 recovery-gate characterization.

These tests verify the existing recovery contract without changing production
behavior:

- valid durable PAPER state is restored before execution can resume;
- semantically incompatible state is rejected;
- failed recovery leaves the runtime blocked;
- no execution side effects occur after failed recovery.
"""

import json

import pytest

from backend.services.durable_execution_state_v2 import seal
from backend.tests.test_durable_crash_recovery_v2 import (
    build_runtime,
    open_position,
    run_crash,
)


def test_valid_recovery_restores_authoritative_state_before_resume(tmp_path):
    path = tmp_path / "state.json"
    run_crash(path, "open")

    lifecycle, account, store, recovery, startup = build_runtime()

    try:
        startup_report = startup.startup_from(file_path=path)

        assert startup_report["success"] is True
        assert startup_report["mode"] == "RECOVERY"
        assert len(lifecycle.get_active_positions()) == 1
        assert len(lifecycle.broker_connector_v2.get_fills()) == 1
        assert len(lifecycle.trade_journal_v2.trades) == 1
        assert account.get_state()["trading_blocked"] is False

        recovered_position = lifecycle.get_active_positions()[0]
        assert recovered_position["status"] == "OPEN"
        assert recovered_position["execution_mode"] == "PAPER"

        recovery_report = recovery.recover_from(file_path=path)
        assert recovery_report["success"] is True

        # The restored authoritative state must be usable by the normal
        # lifecycle after validation; closing the recovered position must not
        # create a second position or fill.
        close_result = lifecycle.update_position(
            position_id=recovered_position["position_id"],
            current_price=120.0,
        )

        assert close_result["updated"] is True
        assert close_result["active_position_removed"] is True
        assert lifecycle.get_active_positions() == []
        assert len(lifecycle.broker_connector_v2.get_fills()) == 1
        assert len(lifecycle.trade_journal_v2.get_closed_trades()) == 1
    finally:
        store._durability.release()


def test_incompatible_recovery_is_rejected_and_execution_remains_blocked(
    tmp_path,
):
    path = tmp_path / "state.json"
    run_crash(path, "open")

    state = json.loads(path.read_text(encoding="utf-8"))
    state["active_positions"][0]["execution_mode"] = "LIVE"

    metadata = state["durability"]
    # seal() hashes an unsigned payload. Preserve a valid envelope so this
    # test reaches semantic LIVE rejection rather than checksum rejection.
    state.pop("checksum")
    incompatible_state = seal(
        state,
        metadata["generation"],
        "COMMITTED",
    )
    path.write_text(
        json.dumps(incompatible_state),
        encoding="utf-8",
    )

    lifecycle, account, store, recovery, startup = build_runtime()

    try:
        with pytest.raises(ValueError, match="PAPER"):
            startup.startup_from(file_path=path)

        assert startup.get_status() == "FAILED"
        assert recovery.get_last_recovery_report()["success"] is False
        assert account.get_state()["trading_blocked"] is True
        assert lifecycle.get_active_positions() == []
        assert lifecycle.broker_connector_v2.get_fills() == []
        assert lifecycle.trade_journal_v2.trades == []

        # Failed semantic recovery must not authorize a new execution.
        with pytest.raises(RuntimeError):
            open_position(lifecycle)

        assert lifecycle.get_active_positions() == []
        assert lifecycle.broker_connector_v2.get_fills() == []
        assert lifecycle.trade_journal_v2.trades == []
    finally:
        store._durability.release()
