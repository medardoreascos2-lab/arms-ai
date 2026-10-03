"""Lucid source profile and fail-closed regression tests."""

from datetime import timedelta
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
    PayoutRequest, RuleStatus, SourceStatus, evaluate_account_v2,
    evaluate_payout_v2,
)
from backend.prop_firms.lucid_profiles import (
    FIRST_PAYOUT_CAP, INITIAL_TRAIL_BALANCES,
    LATER_PAYOUT_CAP, LUCID_PROGRAM_SUPPORT, MAXIMUM_LOSSES, MAXIMUM_UNITS,
    MINIMUM_CYCLE_PROFIT, PROFIT_TARGETS, REVIEWED_AT, SIZES,
    evaluation_profile, funded_fixed_dll_profile, funded_no_dll_profile,
    funded_scaling_dll_profile, standard_lucid_profiles,
)

NOW = REVIEWED_AT + timedelta(days=1)


def outcome(result, rule_id):
    return next(item for item in result.outcomes if item.rule_id == rule_id)


def session_values():
    return dict(
        session_id="lucid-session", daily_pnl_session_id="lucid-session",
        session_ends_at=NOW + timedelta(hours=3), prior_session_blocked=False,
    )


def evaluation_snapshot(size=D("50000"), **changes):
    target = PROFIT_TARGETS[size]
    balance = size + target
    values = dict(
        as_of=NOW, stage=AccountStage.EVALUATION, starting_balance=size,
        current_balance=balance, current_equity=balance,
        highest_end_of_day_balance=balance, daily_pnl=D("0"),
        total_profit=target, realized_pnl=target, withdrawals=D("0"),
        contracts_open=0, working_orders=0, contracts_traded=0,
        exposures=(ExposurePosition("NQ", int(MAXIMUM_UNITS[size])),),
        trading_days=1, prior_account_failed=False, **session_values(),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def funded_snapshot(size=D("50000"), *, payout_count=0, **changes):
    balance = INITIAL_TRAIL_BALANCES[size] + FIRST_PAYOUT_CAP[size]
    profit = balance - size
    cycle_profit = MINIMUM_CYCLE_PROFIT[size]
    values = dict(
        as_of=NOW, stage=AccountStage.FUNDED, starting_balance=size,
        current_balance=balance, current_equity=balance,
        highest_end_of_day_balance=balance, daily_pnl=D("0"),
        total_profit=profit, realized_pnl=profit, withdrawals=D("0"),
        contracts_open=0, working_orders=0, contracts_traded=0,
        exposures=(ExposurePosition("MNQ", int(MAXIMUM_UNITS[size] * 10)),),
        prior_account_failed=False,
        payout_cycle=PayoutCycleSnapshot(
            cycle_id="lucid-cycle", payout_count=payout_count,
            current_cycle_start=NOW - timedelta(days=2),
            withdrawals_total=D("0"), profit_since_last_payout=cycle_profit,
            best_day_profit_since_last_payout=cycle_profit * D("0.40"),
        ),
        **session_values(),
    )
    values.update(changes)
    return AccountSnapshot(**values)


def test_standard_matrix_keeps_lucidpro_dll_options_distinct():
    profiles = standard_lucid_profiles()
    assert len(profiles) == 16
    assert {profile.account_size for profile in profiles} == set(SIZES)
    assert {profile.program_id for profile in profiles} == {
        "lucidpro_evaluation", "lucidpro_funded_no_dll",
        "lucidpro_funded_fixed_dll", "lucidpro_funded_scaling_dll",
    }
    assert len({profile.config_hash for profile in profiles}) == 16


@pytest.mark.parametrize("size", SIZES)
def test_evaluation_matrix_preserves_official_boundaries(size):
    profile = evaluation_profile(size)
    assert profile.profit_target == PROFIT_TARGETS[size]
    assert profile.drawdown.maximum_loss == MAXIMUM_LOSSES[size]
    assert profile.drawdown.floor_cap == size + D("100")
    assert profile.contract_limit.weighted_exposure.maximum_units == MAXIMUM_UNITS[size]
    result = evaluate_account_v2(profile, evaluation_snapshot(size))
    assert outcome(result, "drawdown").status == RuleStatus.PASS
    assert outcome(result, "contracts").status == RuleStatus.PASS
    assert outcome(result, "profit_target").status == RuleStatus.PASS
    assert not result.account_valid and not result.trading_allowed_now
    assert "INCOMPLETE" in result.blocking_reasons


def test_evaluation_daily_loss_is_soft_session_block_and_25k_has_none():
    blocked = evaluate_account_v2(
        evaluation_profile(D("50000")),
        evaluation_snapshot(D("50000"), daily_pnl=D("-1200")),
    )
    assert not blocked.account_failed
    assert outcome(blocked, "daily_loss").status == RuleStatus.SESSION_BLOCKED
    no_dll = evaluate_account_v2(
        evaluation_profile(D("25000")),
        evaluation_snapshot(D("25000"), daily_pnl=D("-9999")),
    )
    assert outcome(no_dll, "daily_loss").status == RuleStatus.NOT_APPLICABLE


def test_eod_drawdown_locks_at_starting_balance_plus_one_hundred():
    profile = evaluation_profile(D("50000"))
    result = evaluate_account_v2(
        profile,
        evaluation_snapshot(
            current_balance=D("50100"), current_equity=D("50100"),
            highest_end_of_day_balance=D("60000"),
        ),
    )
    assert result.metric("effective_drawdown_floor") == D("50100")
    assert result.account_failed


def test_weighted_mini_micro_boundary_and_unknown_product_fail_closed():
    profile = evaluation_profile(D("25000"))
    boundary = evaluate_account_v2(
        profile,
        evaluation_snapshot(D("25000"), exposures=(ExposurePosition("MNQ", 20),)),
    )
    assert boundary.metric("weighted_exposure_total") == D("2.0")
    assert outcome(boundary, "contracts").status == RuleStatus.PASS
    breach = evaluate_account_v2(
        profile,
        evaluation_snapshot(D("25000"), exposures=(ExposurePosition("MNQ", 21),)),
    )
    assert breach.account_failed
    unknown = evaluate_account_v2(
        profile,
        evaluation_snapshot(D("25000"), exposures=(ExposurePosition("UNKNOWN", 1),)),
    )
    assert outcome(unknown, "contracts").status == RuleStatus.INCOMPLETE_DATA
    assert not unknown.trading_allowed_now


def test_funded_dll_variants_are_explicit_and_25k_conflict_is_preserved():
    no_dll = funded_no_dll_profile(D("50000"))
    fixed = funded_fixed_dll_profile(D("50000"))
    scaling = funded_scaling_dll_profile(D("50000"))
    assert no_dll.daily_loss.limit is None
    assert fixed.daily_loss.limit == D("1200")
    assert scaling.daily_loss.scaling_fraction_of_peak_eod_profit == D("0.60")
    assert funded_fixed_dll_profile(D("25000")).source_review.status == SourceStatus.SOURCE_CONFLICT
    assert funded_fixed_dll_profile(D("25000")).daily_loss.limit == D("600")


def test_lucidscale_activates_only_after_closing_above_initial_trail():
    profile = funded_scaling_dll_profile(D("50000"))
    exact = evaluate_account_v2(
        profile,
        funded_snapshot(
            highest_end_of_day_balance=D("52100"), daily_pnl=D("-1200"),
            current_balance=D("52100"), current_equity=D("52100"),
        ),
    )
    assert outcome(exact, "daily_loss").status == RuleStatus.SESSION_BLOCKED
    scaled = evaluate_account_v2(
        profile,
        funded_snapshot(
            highest_end_of_day_balance=D("53000"), daily_pnl=D("-1799"),
            current_balance=D("53000"), current_equity=D("53000"),
        ),
    )
    assert outcome(scaled, "daily_loss").status == RuleStatus.PASS
    breach = evaluate_account_v2(
        profile,
        funded_snapshot(
            highest_end_of_day_balance=D("53000"), daily_pnl=D("-1800"),
            current_balance=D("53000"), current_equity=D("53000"),
        ),
    )
    assert outcome(breach, "daily_loss").status == RuleStatus.SESSION_BLOCKED


def test_lucidscale_25k_has_no_dll_before_activation_and_dynamic_after():
    profile = funded_scaling_dll_profile(D("25000"))
    before = evaluate_account_v2(
        profile,
        funded_snapshot(
            D("25000"), highest_end_of_day_balance=D("26100"),
            current_balance=D("26100"), current_equity=D("26100"),
            daily_pnl=D("-5000"),
        ),
    )
    assert outcome(before, "daily_loss").status == RuleStatus.NOT_APPLICABLE
    after = evaluate_account_v2(
        profile,
        funded_snapshot(
            D("25000"), highest_end_of_day_balance=D("27000"),
            current_balance=D("27000"), current_equity=D("27000"),
            daily_pnl=D("-1200"),
        ),
    )
    assert outcome(after, "daily_loss").status == RuleStatus.SESSION_BLOCKED


def test_lucidscale_missing_peak_eod_data_blocks_trading():
    result = evaluate_account_v2(
        funded_scaling_dll_profile(D("50000")),
        funded_snapshot(highest_end_of_day_balance=None),
    )
    assert outcome(result, "daily_loss").status == RuleStatus.INCOMPLETE_DATA
    assert "MISSING_PEAK_END_OF_DAY_BALANCE_FOR_DAILY_LOSS" in result.blocking_reasons
    assert not result.trading_allowed_now

    invalid = evaluate_account_v2(
        funded_scaling_dll_profile(D("50000")),
        funded_snapshot(highest_end_of_day_balance=D("49999")),
    )
    assert "INVALID_PEAK_END_OF_DAY_PROFIT_FOR_DAILY_LOSS" in invalid.blocking_reasons
    assert not invalid.trading_allowed_now


def test_payout_cycle_enforces_profit_consistency_buffer_cap_and_split():
    size = D("50000")
    profile = funded_no_dll_profile(size)
    request = PayoutRequest(FIRST_PAYOUT_CAP[size])
    result = evaluate_payout_v2(profile, funded_snapshot(size), request)
    assert "PAYOUT_CYCLE_PROFIT_NOT_MET" not in result.blocking_reasons
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" not in result.blocking_reasons
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" not in result.blocking_reasons
    assert "PAYOUT_MINIMUM_BALANCE_NOT_MET" not in result.blocking_reasons
    assert result.metric("post_payout_balance") == INITIAL_TRAIL_BALANCES[size]
    assert result.metric("estimated_trader_payout") == D("1800.00")
    assert not result.payout_eligible  # source review is fail-closed until hours are modeled


def test_payout_exact_forty_percent_passes_and_above_fails():
    profile = funded_no_dll_profile(D("50000"))
    exact = evaluate_payout_v2(profile, funded_snapshot(), PayoutRequest(D("500")))
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" not in exact.blocking_reasons
    bad_cycle = PayoutCycleSnapshot(
        cycle_id="bad", payout_count=0, current_cycle_start=NOW - timedelta(days=1),
        withdrawals_total=D("0"), profit_since_last_payout=D("500"),
        best_day_profit_since_last_payout=D("200.01"),
    )
    above = evaluate_payout_v2(
        profile, funded_snapshot(payout_cycle=bad_cycle), PayoutRequest(D("500")),
    )
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" in above.blocking_reasons


def test_second_payout_cap_and_fifth_payout_transition_boundary():
    size = D("50000")
    profile = funded_no_dll_profile(size)
    second = evaluate_payout_v2(
        profile,
        funded_snapshot(size, payout_count=1,
                        current_balance=INITIAL_TRAIL_BALANCES[size] + LATER_PAYOUT_CAP[size]),
        PayoutRequest(LATER_PAYOUT_CAP[size]),
    )
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" not in second.blocking_reasons
    final_reached = evaluate_payout_v2(
        profile, funded_snapshot(size, payout_count=5), PayoutRequest(D("500")),
    )
    assert "PAYOUT_COUNT_LIMIT_REACHED" in final_reached.blocking_reasons


def test_program_support_keeps_current_legacy_and_live_routes_separate():
    support = {item.program_id: item for item in LUCID_PROGRAM_SUPPORT}
    assert support["lucidpro_evaluation"].next_stage == AccountStage.FUNDED
    assert support["lucidpro_funded"].next_stage == AccountStage.LIVE
    assert support["lucidlive"].stage == AccountStage.LIVE
    assert not support["lucidlive"].executable
    assert "LIVE_EXECUTION_UNSUPPORTED" in support["lucidlive"].reason
    assert support["lucidblack_legacy"].program_id.endswith("legacy")
    assert all(not item.executable for item in support.values())


def test_unsupported_size_is_rejected():
    with pytest.raises(ValueError):
        evaluation_profile(D("75000"))
