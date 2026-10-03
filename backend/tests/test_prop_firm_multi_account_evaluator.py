"""Independent multi-account prop-firm evaluation tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutRequest,
    PropFirmAccountSnapshot, RuleStatus, SourceStatus,
    canonical_profile_registry, evaluate_accounts,
)
from backend.prop_firms.apex_profiles import VERSION as APEX_VERSION
from backend.prop_firms.topstep_profiles import REVIEWED_AT as TOPSTEP_REVIEWED_AT

NOW = datetime(2026, 10, 4, 15, 0, tzinfo=timezone.utc)


def topstep_state(at=NOW, **changes):
    values = dict(
        as_of=at, stage=AccountStage.EVALUATION, starting_balance=D("50000"),
        current_balance=D("53000"), current_equity=D("53000"),
        highest_end_of_day_balance=D("53000"), daily_pnl=D("0"),
        total_profit=D("3000"), realized_pnl=D("3000"),
        best_day_profit=D("1500"), withdrawals=D("0"), trading_days=2,
        contracts_open=0, contracts_traded=0,
        exposures=(ExposurePosition("NQ", 1),), prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def apex_state(**changes):
    values = dict(
        as_of=NOW, account_started_at=NOW - timedelta(days=2),
        stage=AccountStage.EVALUATION, starting_balance=D("50000"),
        current_balance=D("53000"), current_equity=D("53000"),
        highest_end_of_day_balance=D("53000"), daily_pnl=D("0"),
        total_profit=D("3000"), realized_pnl=D("3000"), withdrawals=D("0"),
        contracts_open=0, contracts_traded=0,
        exposures=(ExposurePosition("NQ", 1),), prior_account_failed=False,
        session_id="apex-s1", daily_pnl_session_id="apex-s1",
        prior_session_blocked=False, session_ends_at=NOW + timedelta(hours=2),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def identified(
    account_id, firm_id, program_id, version, state, *, size=D("50000"),
):
    return PropFirmAccountSnapshot(
        account_id=account_id, firm_id=firm_id, program_id=program_id,
        profile_version=version, stage=state.stage, account_size=size,
        captured_at=state.as_of, data_source=f"runtime://paper/{account_id}",
        simulated=True, state=state,
    )


def test_heterogeneous_accounts_are_evaluated_independently():
    healthy = identified(
        "topstep-1", "topstep", "trading_combine",
        "2026-10-03/no-dll", topstep_state(),
    )
    failed = identified(
        "apex-1", "apex", "eod_evaluation_rithmic", APEX_VERSION,
        apex_state(current_balance=D("50000"), current_equity=D("50000")),
    )
    summary = evaluate_accounts(canonical_profile_registry(), (healthy, failed))
    by_id = {item.account_id: item for item in summary.accounts}
    assert by_id["topstep-1"].account_valid
    assert by_id["topstep-1"].trading_allowed_now
    assert by_id["topstep-1"].objective_status == "MET"
    assert by_id["topstep-1"].drawdown_state.status == RuleStatus.PASS
    assert by_id["apex-1"].account_failed
    assert not by_id["apex-1"].trading_allowed_now
    assert by_id["apex-1"].drawdown_state.status == RuleStatus.ACCOUNT_FAILED
    assert summary.total_accounts == 2
    assert summary.valid_accounts == 1
    assert summary.failed_accounts == 1
    assert summary.trading_allowed_accounts == 1
    assert summary.blocked_accounts == 1
    assert not summary.execution_authorized
    assert all(not item.execution_authorized for item in summary.accounts)


def test_missing_profile_blocks_only_that_account():
    healthy = identified(
        "topstep-1", "topstep", "trading_combine",
        "2026-10-03/no-dll", topstep_state(),
    )
    missing = identified(
        "missing-1", "unknown", "missing", "v1", topstep_state(),
    )
    summary = evaluate_accounts(canonical_profile_registry(), (missing, healthy))
    assert summary.accounts[0].blocking_reasons == (
        "PROFILE_RESOLUTION_PROFILENOTFOUNDERROR",
    )
    assert summary.accounts[0].source_status is None
    assert summary.accounts[0].drawdown_state.status == RuleStatus.INCOMPLETE_DATA
    assert summary.accounts[1].account_valid


def test_incomplete_source_profile_is_blocked_before_rule_evaluation_by_default():
    state = replace(
        topstep_state(), stage=AccountStage.FUNDED,
        highest_end_of_day_balance=D("54100"),
    )
    lucid = identified(
        "lucid-1", "lucid", "lucidpro_funded_no_dll", "2026-10-03", state,
    )
    result = evaluate_accounts(canonical_profile_registry(), (lucid,)).accounts[0]
    assert result.source_status == SourceStatus.INCOMPLETE
    assert result.blocking_reasons == ("PROFILE_SOURCE_STATUS_INCOMPLETE",)
    assert result.profile_identity is None
    assert not result.account_valid and not result.trading_allowed_now


def test_explicit_unverified_analysis_keeps_source_block_and_numeric_states_visible():
    state = replace(
        topstep_state(), stage=AccountStage.FUNDED,
        current_balance=D("54100"), current_equity=D("54100"),
        highest_end_of_day_balance=D("54100"),
    )
    lucid = identified(
        "lucid-1", "lucid", "lucidpro_funded_no_dll", "2026-10-03", state,
    )
    result = evaluate_accounts(
        canonical_profile_registry(), (lucid,), require_current_sources=False,
    ).accounts[0]
    assert result.profile_identity is not None
    assert result.source_status == SourceStatus.INCOMPLETE
    assert result.drawdown_state.status == RuleStatus.PASS
    assert result.exposure_state.status == RuleStatus.PASS
    assert "INCOMPLETE" in result.blocking_reasons
    assert not result.account_valid and not result.execution_authorized


def test_payout_request_is_read_only_and_reported_per_account():
    snapshot = identified(
        "topstep-1", "topstep", "trading_combine",
        "2026-10-03/no-dll", topstep_state(),
    )
    before_hash = snapshot.content_hash
    result = evaluate_accounts(
        canonical_profile_registry(), (snapshot,),
        payout_requests={snapshot.account_id: PayoutRequest(D("500"))},
    ).accounts[0]
    assert result.payout_evaluated
    assert result.payout_status == "INELIGIBLE"
    assert "PAYOUT_DISABLED" in result.blocking_reasons
    assert snapshot.content_hash == before_hash
    assert snapshot.state.current_balance == D("53000")
    assert not result.execution_authorized


def test_stale_profile_blocks_only_affected_account():
    stale_at = TOPSTEP_REVIEWED_AT + timedelta(days=31)
    stale = identified(
        "stale-1", "topstep", "trading_combine", "2026-10-03/no-dll",
        topstep_state(at=stale_at),
    )
    result = evaluate_accounts(canonical_profile_registry(), (stale,)).accounts[0]
    assert result.source_status == SourceStatus.STALE_REVIEW_REQUIRED
    assert result.blocking_reasons == (
        "PROFILE_SOURCE_STATUS_STALE_REVIEW_REQUIRED",
    )


def test_duplicate_accounts_and_unknown_payout_request_are_rejected():
    snapshot = identified(
        "topstep-1", "topstep", "trading_combine",
        "2026-10-03/no-dll", topstep_state(),
    )
    with pytest.raises(ValueError, match="unique"):
        evaluate_accounts(canonical_profile_registry(), (snapshot, snapshot))
    with pytest.raises(ValueError, match="unknown account"):
        evaluate_accounts(
            canonical_profile_registry(), (snapshot,),
            payout_requests={"other": PayoutRequest(D("500"))},
        )


def test_input_container_and_payout_map_types_are_validated():
    snapshot = identified(
        "topstep-1", "topstep", "trading_combine",
        "2026-10-03/no-dll", topstep_state(),
    )
    with pytest.raises(ValueError, match="immutable tuple"):
        evaluate_accounts(canonical_profile_registry(), [snapshot])
    with pytest.raises(ValueError, match="PayoutRequest"):
        evaluate_accounts(
            canonical_profile_registry(), (snapshot,),
            payout_requests={snapshot.account_id: D("500")},
        )
