"""Source-backed Topstep profile regression tests."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
    PayoutRequest, RuleStatus, SourceStatus, evaluate_account_v2,
    evaluate_payout_v2,
)
from backend.prop_firms.topstep_profiles import (
    CONSISTENCY_CAPS, DAILY_LOSSES, MAXIMUM_LOSSES, MAXIMUM_MINIS,
    PROFIT_TARGETS, PROMO_SOURCE, REVIEWED_AT, SIZES, STANDARD_CAPS,
    TOPSTEP_PROGRAM_SUPPORT, express_funded_consistency_profile,
    express_funded_standard_profile, standard_topstep_profiles,
    trading_combine_profile,
)

NOW = REVIEWED_AT + timedelta(days=1)


def cycle(**changes):
    values = dict(
        cycle_id="topstep-cycle", payout_count=0,
        current_cycle_start=REVIEWED_AT,
        withdrawals_total=D("0"), profit_since_last_payout=D("3000"),
        winning_days_since_last_payout=5,
        trading_days_since_last_payout=5,
        best_day_profit_since_last_payout=D("1000"),
    )
    values.update(changes)
    return PayoutCycleSnapshot(**values)


def combine_snapshot(size=D("50000"), **changes):
    target = PROFIT_TARGETS[size]
    values = dict(
        as_of=NOW, stage=AccountStage.EVALUATION, starting_balance=size,
        current_balance=size + target, current_equity=size + target,
        highest_end_of_day_balance=size + target,
        daily_pnl=D("0"), total_profit=target, realized_pnl=target,
        best_day_profit=target * D("0.55"), withdrawals=D("0"),
        contracts_open=0, contracts_traded=0, trading_days=2,
        exposures=(ExposurePosition("NQ", int(MAXIMUM_MINIS[size])),),
        prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def xfa_snapshot(size=D("50000"), **changes):
    values = dict(
        as_of=NOW, stage=AccountStage.EXPRESS, starting_balance=D("0"),
        current_balance=D("6000"), current_equity=D("6000"),
        highest_end_of_day_balance=D("6000"), daily_pnl=D("0"),
        total_profit=D("6000"), realized_pnl=D("6000"),
        best_day_profit=D("1500"), withdrawals=D("0"),
        contracts_open=0, contracts_traded=0, trading_days=5,
        payout_cycle=cycle(), prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def outcome(result, rule_id):
    return next(item for item in result.outcomes if item.rule_id == rule_id)


def reasons(result, rule_id=None):
    return tuple(item.reason for item in result.outcomes
                 if rule_id is None or item.rule_id == rule_id)


def test_standard_matrix_covers_sizes_paths_and_dll_variants():
    profiles = standard_topstep_profiles()
    assert len(profiles) == 18
    assert {profile.account_size for profile in profiles} == set(SIZES)
    assert {profile.program_id for profile in profiles} == {
        "trading_combine", "express_funded_standard", "express_funded_consistency"
    }
    assert len({profile.config_hash for profile in profiles}) == 18


@pytest.mark.parametrize("size", SIZES)
def test_trading_combine_verified_size_matrix(size):
    profile = trading_combine_profile(size)
    assert profile.source_review.status == SourceStatus.CURRENT_VERIFIED
    assert profile.profit_target == PROFIT_TARGETS[size]
    assert profile.drawdown.maximum_loss == MAXIMUM_LOSSES[size]
    assert profile.contract_limit.weighted_exposure.maximum_units == MAXIMUM_MINIS[size]
    result = evaluate_account_v2(profile, combine_snapshot(size), require_current_sources=True)
    assert result.account_valid and result.trading_allowed_now
    assert result.stage_objective_met


def test_combine_weighted_exposure_accepts_ten_to_one_boundary():
    profile = trading_combine_profile(D("50000"))
    boundary = combine_snapshot(exposures=(
        ExposurePosition("NQ", 4), ExposurePosition("MNQ", 10),
    ))
    result = evaluate_account_v2(profile, boundary)
    assert result.metric("weighted_exposure_total") == D("5")
    assert outcome(result, "contracts").status == RuleStatus.PASS


def test_combine_contract_breach_blocks_trading_without_failing_account():
    profile = trading_combine_profile(D("50000"))
    result = evaluate_account_v2(
        profile, combine_snapshot(exposures=(ExposurePosition("MNQ", 51),))
    )
    assert result.account_valid and not result.account_failed
    assert not result.trading_allowed_now
    assert outcome(result, "contracts").status == RuleStatus.TRADING_BLOCKED
    assert "WEIGHTED_EXPOSURE_LIMIT_BREACHED" in result.blocking_reasons


def test_unmapped_combine_product_fails_closed():
    profile = trading_combine_profile(D("50000"))
    result = evaluate_account_v2(
        profile, combine_snapshot(exposures=(ExposurePosition("UNKNOWN", 1),))
    )
    assert not result.trading_allowed_now
    assert outcome(result, "contracts").status == RuleStatus.INCOMPLETE_DATA
    assert "UNSUPPORTED_EXPOSURE_MAPPING" in result.blocking_reasons


def test_combine_objectives_are_inclusive_boundaries():
    profile = trading_combine_profile(D("50000"))
    passing = evaluate_account_v2(profile, combine_snapshot())
    assert passing.stage_objective_met
    high_best_day = evaluate_account_v2(
        profile, combine_snapshot(best_day_profit=D("1650.01"))
    )
    assert not high_best_day.stage_objective_met
    assert "CONSISTENCY_LIMIT_BREACHED" in high_best_day.blocking_reasons
    one_day = evaluate_account_v2(profile, combine_snapshot(trading_days=1))
    assert "MINIMUM_TRADING_DAYS_NOT_MET" in one_day.blocking_reasons


def test_combine_mll_uses_eod_high_and_never_descends_below_start():
    profile = trading_combine_profile(D("50000"))
    result = evaluate_account_v2(
        profile,
        combine_snapshot(current_balance=D("49999.99"), current_equity=D("49999.99"),
                         highest_end_of_day_balance=D("53000")),
    )
    assert result.metric("effective_drawdown_floor") == D("50000")
    assert result.account_failed
    assert "DRAWDOWN_LIMIT_BREACHED" in result.failure_reasons


def test_optional_dll_blocks_only_current_trading_day():
    size = D("50000")
    profile = trading_combine_profile(size, dll_enabled=True)
    ending = NOW + timedelta(hours=8)
    result = evaluate_account_v2(
        profile,
        combine_snapshot(size, daily_pnl=-DAILY_LOSSES[size], session_id="day-1",
                         daily_pnl_session_id="day-1", prior_session_blocked=False,
                         trading_day_ends_at=ending),
    )
    daily = outcome(result, "daily_loss")
    assert result.account_valid and not result.account_failed
    assert not result.trading_allowed_now
    assert daily.status == RuleStatus.SESSION_BLOCKED and daily.reset_at == ending


@pytest.mark.parametrize("factory", [
    express_funded_standard_profile, express_funded_consistency_profile,
])
def test_xfa_is_explicitly_incomplete_and_contract_gap_fails_closed(factory):
    profile = factory(D("50000"))
    assert profile.starting_balance == 0 and profile.allow_zero_starting_balance
    assert profile.source_review.status == SourceStatus.INCOMPLETE
    result = evaluate_account_v2(profile, xfa_snapshot())
    assert not result.account_valid and not result.trading_allowed_now
    assert outcome(result, "contracts").reason == "SCALING_PLAN_TIER_DATA_UNAVAILABLE"
    assert outcome(result, "contracts").status == RuleStatus.INCOMPLETE_DATA


def test_xfa_first_payout_locks_drawdown_floor_at_zero():
    profile = express_funded_standard_profile(D("50000"))
    result = evaluate_account_v2(
        profile,
        xfa_snapshot(current_balance=D("1000"), current_equity=D("1000"),
                     payout_cycle=cycle(payout_count=1)),
    )
    assert result.metric("effective_drawdown_floor") == D("0")
    assert result.metric("drawdown_model_phase") == "POST_EVENT_FIXED"


def test_xfa_standard_payout_limits_and_cycle_reset_inputs():
    profile = express_funded_standard_profile(D("50000"))
    base = xfa_snapshot()
    at_cap = evaluate_payout_v2(profile, base, PayoutRequest(STANDARD_CAPS[D("50000")]))
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" not in reasons(at_cap, "payout_amount")
    over_cap = evaluate_payout_v2(
        profile, base, PayoutRequest(STANDARD_CAPS[D("50000")] + D("0.01"))
    )
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" in reasons(over_cap, "payout_amount")
    insufficient_days = evaluate_payout_v2(
        profile,
        xfa_snapshot(payout_cycle=cycle(winning_days_since_last_payout=4)),
        PayoutRequest(D("125")),
    )
    assert "PAYOUT_CYCLE_WINNING_DAYS_NOT_MET" in insufficient_days.blocking_reasons


def test_xfa_consistency_payout_boundary():
    profile = express_funded_consistency_profile(D("50000"))
    passing = evaluate_payout_v2(profile, xfa_snapshot(), PayoutRequest(D("125")))
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" not in passing.blocking_reasons
    failing = evaluate_payout_v2(
        profile,
        xfa_snapshot(payout_cycle=cycle(best_day_profit_since_last_payout=D("1200.01"))),
        PayoutRequest(D("125")),
    )
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" in failing.blocking_reasons
    assert profile.payout.maximum_payout_amount == CONSISTENCY_CAPS[D("50000")]


def test_temporary_promotion_is_opt_in_and_review_required():
    normal = express_funded_standard_profile(D("50000"))
    promo = express_funded_standard_profile(D("50000"), promotional_cap=True)
    assert normal.payout.maximum_payout_amount == D("2000")
    assert promo.payout.maximum_payout_amount == D("4000")
    assert PROMO_SOURCE.temporary and PROMO_SOURCE.review_required
    assert promo.source_review.review_due_at == REVIEWED_AT + timedelta(days=1)


def test_source_review_expiry_warns_and_can_be_required_fail_closed():
    profile = trading_combine_profile(D("50000"))
    stale_time = profile.source_review.review_due_at + timedelta(seconds=1)
    stale = combine_snapshot(as_of=stale_time)
    warning = evaluate_account_v2(profile, stale)
    assert warning.source_status == SourceStatus.STALE_REVIEW_REQUIRED
    assert "STALE_REVIEW_REQUIRED" in warning.warnings
    required = evaluate_account_v2(profile, stale, require_current_sources=True)
    assert not required.account_valid and not required.trading_allowed_now


def test_profile_hash_is_deterministic_and_changes_with_variant():
    first = trading_combine_profile(D("50000"))
    second = trading_combine_profile(D("50000"))
    dll = trading_combine_profile(D("50000"), dll_enabled=True)
    assert first.config_hash == second.config_hash
    assert first.config_hash != dll.config_hash
    assert replace(first, version="changed").config_hash != first.config_hash


def test_live_and_pro_are_distinct_unsupported_program_records():
    support = {item.program_id: item for item in TOPSTEP_PROGRAM_SUPPORT}
    assert support["live_funded"].stage == AccountStage.LIVE
    assert support["pro_account"].stage == AccountStage.PRO
    assert not support["live_funded"].implemented
    assert not support["pro_account"].implemented
    assert support["live_funded"].reason != support["pro_account"].reason
