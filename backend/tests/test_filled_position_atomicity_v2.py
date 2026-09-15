from __future__ import annotations

import pytest

from backend.tests.test_phase1_fill_atomicity_v2 import (
    build_durable_service,
    submit_valid_signal,
)


def test_filled_execution_without_open_position_rolls_back_all_financial_surfaces(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, store = build_durable_service(tmp_path)

    broker = service.broker_connector_v2
    portfolio = service.portfolio_manager_v2
    journal = service.trade_journal_v2

    account_state_manager = (
        portfolio.account_state_manager_v2
    )

    before_account_state = (
        account_state_manager.get_state()
    )

    def reject_position_open(*, execution):
        assert execution["accepted"] is True
        assert (
            str(execution["status"]).strip().upper()
            == "FILLED"
        )

        return {
            "opened": False,
            "reason": "simulated_position_open_failure",
        }

    monkeypatch.setattr(
        service.position_manager,
        "open_position",
        reject_position_open,
    )

    with pytest.raises(
        RuntimeError,
        match="filled_execution_position_open_failed",
    ):
        submit_valid_signal(service)

    assert service.get_active_positions() == []
    assert portfolio.get_open_positions() == []
    assert broker.get_orders() == []
    assert broker.get_fills() == []

    assert journal.get_summary()["open_trades"] == 0

    after_account_state = (
        account_state_manager.get_state()
    )

    assert (
        after_account_state["open_positions"]
        == before_account_state["open_positions"]
    )

    assert (
        after_account_state["daily_pnl"]
        == before_account_state["daily_pnl"]
    )
