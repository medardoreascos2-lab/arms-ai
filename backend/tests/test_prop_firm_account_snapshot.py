"""Immutable identified prop-firm account snapshot tests."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
    PropFirmAccountSnapshot,
)

NOW = datetime(2026, 10, 4, 14, 30, tzinfo=timezone.utc)


def rule_state(**changes):
    values = dict(
        as_of=NOW, account_started_at=NOW - timedelta(days=20),
        stage=AccountStage.FUNDED, starting_balance=D("50000"),
        current_balance=D("53200"), current_equity=D("53150"),
        realized_pnl=D("3200"), unrealized_pnl=D("-50"), daily_pnl=D("250"),
        highest_balance=D("53400"), highest_equity=D("53500"),
        highest_end_of_day_balance=D("53300"),
        prior_end_of_day_balance=D("53000"), contracts_open=2,
        working_orders=1, contracts_traded=4, trading_days=8,
        best_day_profit=D("600"), total_profit=D("3200"), withdrawals=D("0"),
        prior_payout_count=1, session_id="session-8",
        daily_pnl_session_id="session-8", prior_session_blocked=False,
        session_ends_at=NOW + timedelta(hours=2), prior_drawdown_floor=D("50100"),
        prior_account_failed=False,
        exposures=(ExposurePosition("NQ", 1), ExposurePosition("MNQ", 10)),
        payout_cycle=PayoutCycleSnapshot(
            cycle_id="cycle-2", payout_count=1,
            current_cycle_start=NOW - timedelta(days=5), withdrawals_total=D("0"),
            profit_since_last_payout=D("1200"), winning_days_since_last_payout=4,
            trading_days_since_last_payout=5,
            best_day_profit_since_last_payout=D("400"),
        ),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def identified_snapshot(state=None, **changes):
    values = dict(
        account_id="lucid-50k-001", firm_id="lucid",
        program_id="lucidpro_funded_no_dll", profile_version="2026-10-03",
        stage=AccountStage.FUNDED, account_size=D("50000"), captured_at=NOW,
        data_source="runtime://paper/account/lucid-50k-001", simulated=True,
        state=state or rule_state(),
    )
    values.update(changes)
    return PropFirmAccountSnapshot(**values)


def test_snapshot_exposes_required_account_and_rule_state_without_transformation():
    snapshot = identified_snapshot()
    assert snapshot.account_id == "lucid-50k-001"
    assert snapshot.firm_id == "lucid"
    assert snapshot.program_id == "lucidpro_funded_no_dll"
    assert snapshot.stage == AccountStage.FUNDED
    assert snapshot.account_size == D("50000")
    assert snapshot.balance == D("53200")
    assert snapshot.equity == D("53150")
    assert snapshot.realized_pnl == D("3200")
    assert snapshot.unrealized_pnl == D("-50")
    assert snapshot.daily_pnl == D("250")
    assert snapshot.highest_balance == D("53400")
    assert snapshot.highest_equity == D("53500")
    assert snapshot.highest_end_of_day_balance == D("53300")
    assert snapshot.open_exposure == (
        ExposurePosition("NQ", 1), ExposurePosition("MNQ", 10),
    )
    assert snapshot.trading_days == 8
    assert snapshot.winning_days == 4
    assert snapshot.best_day_profit == D("600")
    assert snapshot.profit_since_payout == D("1200")
    assert snapshot.payout_cycle.cycle_id == "cycle-2"
    assert snapshot.hard_breach_state is False
    assert snapshot.session_block_state is False
    assert snapshot.to_rule_snapshot() is snapshot.state


def test_snapshot_is_immutable_and_content_hash_covers_identity_and_state():
    snapshot = identified_snapshot()
    assert len(snapshot.content_hash) == 64
    assert snapshot.content_hash == identified_snapshot().content_hash
    assert snapshot.content_hash != identified_snapshot(
        state=rule_state(current_balance=D("53200.01"))
    ).content_hash
    assert snapshot.content_hash != identified_snapshot(
        account_id="lucid-50k-002"
    ).content_hash
    with pytest.raises(FrozenInstanceError):
        snapshot.account_id = "changed"


def test_missing_optional_risk_data_is_preserved_for_fail_closed_evaluation():
    state = rule_state(
        current_equity=None, daily_pnl=None, highest_end_of_day_balance=None,
        exposures=None, trading_days=None, best_day_profit=None,
        payout_cycle=None, prior_account_failed=None, prior_session_blocked=None,
    )
    snapshot = identified_snapshot(state=state)
    assert snapshot.equity is None
    assert snapshot.daily_pnl is None
    assert snapshot.highest_end_of_day_balance is None
    assert snapshot.open_exposure is None
    assert snapshot.trading_days is None
    assert snapshot.winning_days is None
    assert snapshot.best_day_profit is None
    assert snapshot.profit_since_payout is None
    assert snapshot.payout_cycle is None
    assert snapshot.hard_breach_state is None
    assert snapshot.session_block_state is None


def test_identity_stage_and_capture_time_must_match_nested_state():
    with pytest.raises(ValueError, match="stage does not match"):
        identified_snapshot(stage=AccountStage.EVALUATION)
    with pytest.raises(ValueError, match="as_of does not match"):
        identified_snapshot(captured_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="known AccountStage"):
        identified_snapshot(
            stage=AccountStage.UNKNOWN,
            state=rule_state(stage=AccountStage.UNKNOWN),
        )


@pytest.mark.parametrize("changes", [
    {"account_id": ""},
    {"firm_id": " "},
    {"program_id": ""},
    {"profile_version": ""},
    {"data_source": ""},
    {"account_size": D("0")},
    {"account_size": D("NaN")},
    {"account_size": 50000.0},
    {"captured_at": datetime(2026, 10, 4)},
    {"simulated": 1},
])
def test_invalid_identity_or_provenance_is_rejected(changes):
    with pytest.raises(ValueError):
        identified_snapshot(**changes)


def test_account_size_is_distinct_from_zero_balance_funded_state():
    zero_state = rule_state(
        starting_balance=D("0"), current_balance=D("500"), current_equity=D("500"),
    )
    snapshot = identified_snapshot(account_size=D("50000"), state=zero_state)
    assert snapshot.account_size == D("50000")
    assert snapshot.state.starting_balance == D("0")


def test_inconsistent_unblocked_session_identity_is_rejected():
    inconsistent = replace(rule_state(), blocked_session_id="session-8")
    with pytest.raises(ValueError, match="unblocked session"):
        identified_snapshot(state=inconsistent)
