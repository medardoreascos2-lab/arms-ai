"""TakeProfitTrader source profile and fail-closed regression tests."""

from datetime import timedelta
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutRequest, RuleStatus,
    SourceStatus, evaluate_account_v2, evaluate_payout_v2,
)
from backend.prop_firms.takeprofittrader_profiles import (
    MAXIMUM_DRAWDOWNS, MAXIMUM_UNITS, PROFIT_TARGETS, REVIEWED_AT, SIZES,
    TAKEPROFITTRADER_STAGE_SUPPORT, pro_plus_profile, pro_profile,
    standard_takeprofittrader_profiles, test_profile as evaluation_profile,
)

NOW = REVIEWED_AT + timedelta(days=1)


def outcome(result, rule_id):
    return next(item for item in result.outcomes if item.rule_id == rule_id)


def evaluation_snapshot(size=D("50000"), **changes):
    target = PROFIT_TARGETS[size]
    values = dict(
        as_of=NOW, stage=AccountStage.EVALUATION, starting_balance=size,
        current_balance=size + target, current_equity=size + target,
        highest_end_of_day_balance=size + target,
        total_profit=target, realized_pnl=target,
        best_day_profit=target * D("0.499"), withdrawals=D("0"),
        contracts_open=0, working_orders=0, contracts_traded=0,
        trading_days=3, exposures=(ExposurePosition("NQ", int(MAXIMUM_UNITS[size])),),
        prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def pro_snapshot(size=D("50000"), **changes):
    drawdown = MAXIMUM_DRAWDOWNS[size]
    balance = size + drawdown + D("500")
    values = dict(
        as_of=NOW, stage=AccountStage.PRO, starting_balance=size,
        current_balance=balance, current_equity=balance,
        highest_equity=balance, total_profit=drawdown + D("500"),
        realized_pnl=drawdown + D("500"), withdrawals=D("0"),
        contracts_open=0, working_orders=0, contracts_traded=0,
        exposures=(ExposurePosition("MNQ", 10),),
        prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def pro_plus_snapshot(size=D("50000"), **changes):
    balance = size + D("3000")
    values = dict(
        as_of=NOW, stage=AccountStage.LIVE, starting_balance=size,
        current_balance=balance, current_equity=balance,
        highest_end_of_day_balance=balance, total_profit=D("3000"),
        realized_pnl=D("3000"), withdrawals=D("0"), contracts_open=0,
        working_orders=0, contracts_traded=0,
        exposures=(ExposurePosition("MNQ", 10),), prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def test_standard_matrix_keeps_test_pro_and_pro_plus_distinct():
    profiles = standard_takeprofittrader_profiles()
    assert len(profiles) == 15
    assert {profile.account_size for profile in profiles} == set(SIZES)
    assert {profile.program_id for profile in profiles} == {"test", "pro", "pro_plus"}
    assert {profile.stage for profile in profiles} == {
        AccountStage.EVALUATION, AccountStage.PRO, AccountStage.LIVE,
    }
    assert len({profile.config_hash for profile in profiles}) == 15


@pytest.mark.parametrize("size", SIZES)
def test_test_account_matrix_uses_official_numeric_boundaries(size):
    profile = evaluation_profile(size)
    assert profile.profit_target == PROFIT_TARGETS[size]
    assert profile.drawdown.maximum_loss == MAXIMUM_DRAWDOWNS[size]
    assert profile.contract_limit.weighted_exposure.maximum_units == MAXIMUM_UNITS[size]
    result = evaluate_account_v2(profile, evaluation_snapshot(size))
    assert outcome(result, "drawdown").status == RuleStatus.PASS
    assert outcome(result, "contracts").status == RuleStatus.PASS
    assert outcome(result, "consistency").status == RuleStatus.PASS
    assert outcome(result, "trading_days").status == RuleStatus.PASS
    assert outcome(result, "profit_target").status == RuleStatus.PASS
    assert not result.account_valid and not result.trading_allowed_now
    assert "INCOMPLETE" in result.blocking_reasons


def test_test_account_has_no_daily_loss_limit():
    result = evaluate_account_v2(
        evaluation_profile(D("50000")), evaluation_snapshot(daily_pnl=D("-99999"))
    )
    assert outcome(result, "daily_loss").status == RuleStatus.NOT_APPLICABLE


def test_test_consistency_is_strictly_below_fifty_percent():
    profile = evaluation_profile(D("50000"))
    exact = evaluate_account_v2(
        profile, evaluation_snapshot(best_day_profit=D("1500"))
    )
    assert outcome(exact, "consistency").status == RuleStatus.OBJECTIVE_PENDING
    assert outcome(exact, "consistency").reason == "CONSISTENCY_LIMIT_BREACHED"
    below = evaluate_account_v2(
        profile, evaluation_snapshot(best_day_profit=D("1499.99"))
    )
    assert outcome(below, "consistency").status == RuleStatus.PASS


def test_test_three_day_and_profit_targets_are_objectives_not_failures():
    profile = evaluation_profile(D("50000"))
    result = evaluate_account_v2(
        profile, evaluation_snapshot(trading_days=2, total_profit=D("2999.99"))
    )
    assert outcome(result, "trading_days").status == RuleStatus.OBJECTIVE_PENDING
    assert outcome(result, "profit_target").status == RuleStatus.OBJECTIVE_PENDING
    assert not result.account_failed


def test_position_limit_hard_breach_and_unknown_product_fail_closed():
    profile = evaluation_profile(D("25000"))
    micro_boundary = evaluate_account_v2(
        profile, evaluation_snapshot(D("25000"), exposures=(ExposurePosition("MNQ", 30),))
    )
    assert micro_boundary.metric("weighted_exposure_total") == D("3")
    assert outcome(micro_boundary, "contracts").status == RuleStatus.PASS
    breach = evaluate_account_v2(
        profile, evaluation_snapshot(D("25000"), exposures=(ExposurePosition("MNQ", 31),))
    )
    assert breach.account_failed
    assert outcome(breach, "contracts").status == RuleStatus.ACCOUNT_FAILED
    unknown = evaluate_account_v2(
        profile, evaluation_snapshot(D("25000"), exposures=(ExposurePosition("UNKNOWN", 1),))
    )
    assert not unknown.trading_allowed_now
    assert outcome(unknown, "contracts").status == RuleStatus.INCOMPLETE_DATA


def test_test_drawdown_uses_eod_high_and_locks_at_starting_balance():
    profile = evaluation_profile(D("50000"))
    result = evaluate_account_v2(
        profile,
        evaluation_snapshot(current_balance=D("50000"), current_equity=D("50000"),
                            highest_end_of_day_balance=D("53000")),
    )
    assert result.metric("effective_drawdown_floor") == D("50000")
    assert result.account_failed


@pytest.mark.parametrize("size", SIZES)
def test_pro_profile_models_intraday_drawdown_and_active_buffer(size):
    profile = pro_profile(size)
    assert profile.stage == AccountStage.PRO
    assert profile.payout.minimum_balance == size + MAXIMUM_DRAWDOWNS[size]
    assert profile.payout.trader_profit_fraction == D("0.80")
    assert profile.payout.require_flat
    result = evaluate_account_v2(profile, pro_snapshot(size))
    assert result.metric("drawdown_model_phase") == "INTRADAY_EQUITY"
    assert outcome(result, "daily_loss").status == RuleStatus.NOT_APPLICABLE
    assert not result.account_valid and not result.trading_allowed_now


def test_pro_payout_preserves_buffer_and_reports_eighty_percent_split():
    size = D("50000")
    profile = pro_profile(size)
    at_buffer = evaluate_payout_v2(profile, pro_snapshot(size), PayoutRequest(D("500")))
    assert "PAYOUT_MINIMUM_BALANCE_NOT_MET" not in at_buffer.blocking_reasons
    assert at_buffer.metric("post_payout_balance") == D("52000")
    assert at_buffer.metric("estimated_trader_payout") == D("400.00")
    inside_buffer = evaluate_payout_v2(
        profile, pro_snapshot(size), PayoutRequest(D("500.01"))
    )
    assert "PAYOUT_MINIMUM_BALANCE_NOT_MET" in inside_buffer.blocking_reasons


def test_pro_payout_requires_no_positions_or_working_orders():
    profile = pro_profile(D("50000"))
    missing = evaluate_payout_v2(
        profile, pro_snapshot(working_orders=None), PayoutRequest(D("100"))
    )
    assert "MISSING_PAYOUT_FLAT_STATE" in missing.blocking_reasons
    open_order = evaluate_payout_v2(
        profile, pro_snapshot(working_orders=1), PayoutRequest(D("100"))
    )
    assert "PAYOUT_REQUIRES_FLAT_ACCOUNT" in open_order.blocking_reasons


def test_pro_plus_is_live_policy_only_and_never_complete():
    profile = pro_plus_profile(D("50000"))
    assert profile.stage == AccountStage.LIVE
    assert profile.payout.minimum_balance is None
    assert profile.payout.trader_profit_fraction == D("0.90")
    assert profile.source_review.status == SourceStatus.INCOMPLETE
    result = evaluate_payout_v2(profile, pro_plus_snapshot(), PayoutRequest(D("500")))
    assert result.metric("drawdown_model_phase") == "END_OF_DAY_BALANCE"
    assert result.metric("estimated_trader_payout") == D("450.00")
    assert not result.account_valid and not result.trading_allowed_now
    assert not result.payout_eligible


def test_stage_transitions_and_unsupported_closure_route_are_explicit():
    support = {item.program_id: item for item in TAKEPROFITTRADER_STAGE_SUPPORT}
    assert support["test"].next_stage == AccountStage.PRO
    assert not support["test"].transition_discretionary
    assert support["pro"].next_stage == AccountStage.LIVE
    assert support["pro"].transition_discretionary
    assert "ACCOUNT_CLOSURE" in support["pro_closure_withdrawal"].reason
    assert all(item.source_status == SourceStatus.INCOMPLETE for item in support.values())
