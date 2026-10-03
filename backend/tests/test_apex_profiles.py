"""Source-backed Apex profile and fail-closed rule regression tests."""

from datetime import timedelta
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
    PayoutRequest, RuleStatus, SourceStatus, evaluate_account_v2,
    evaluate_payout_v2,
)
from backend.prop_firms.apex_profiles import (
    APEX_PROGRAM_SUPPORT, EOD_PAYOUT_CAPS, EOD_QUALIFYING_DAY,
    EVALUATION_DAILY_LOSSES, EVALUATION_MAXIMUM_UNITS, MAXIMUM_DRAWDOWNS,
    INTRADAY_PAYOUT_CAPS, INTRADAY_QUALIFYING_DAY, PROFIT_TARGETS,
    REVIEWED_AT, SCALING_TIERS, SIZES,
    eod_evaluation_profile, eod_performance_profile,
    intraday_evaluation_profile, intraday_performance_profile,
    standard_apex_profiles,
)

NOW = REVIEWED_AT + timedelta(days=1)


def outcome(result, rule_id):
    return next(item for item in result.outcomes if item.rule_id == rule_id)


def payout_cycle(size=D("25000"), **changes):
    values = dict(
        cycle_id="apex-cycle", payout_count=0, current_cycle_start=REVIEWED_AT,
        withdrawals_total=D("0"), profit_since_last_payout=D("5000"),
        winning_days_since_last_payout=5, trading_days_since_last_payout=5,
        best_day_profit_since_last_payout=D("2499.99"),
        qualifying_days_since_last_payout=5,
        qualifying_day_profit_threshold=EOD_QUALIFYING_DAY[size],
    )
    values.update(changes)
    return PayoutCycleSnapshot(**values)


def evaluation_snapshot(size=D("50000"), *, kind="eod", **changes):
    target = PROFIT_TARGETS[size]
    values = dict(
        as_of=NOW, account_started_at=NOW - timedelta(days=5),
        stage=AccountStage.EVALUATION, starting_balance=size,
        current_balance=size + target, current_equity=size + target,
        highest_end_of_day_balance=size + target,
        highest_equity=size + target, daily_pnl=D("0"), total_profit=target,
        realized_pnl=target, withdrawals=D("0"), contracts_open=0,
        contracts_traded=0, trading_days=1,
        exposures=(ExposurePosition("NQ", int(EVALUATION_MAXIMUM_UNITS[size])),),
        prior_account_failed=False,
    )
    if kind == "eod":
        values.update(
            session_id="session-1", daily_pnl_session_id="session-1",
            prior_session_blocked=False, session_ends_at=NOW + timedelta(hours=8),
        )
    values.update(changes)
    return AccountSnapshot(**values)


def performance_snapshot(size=D("25000"), *, kind="eod", **changes):
    balance = size + D("5000")
    values = dict(
        as_of=NOW, account_started_at=NOW - timedelta(days=31),
        stage=AccountStage.PERFORMANCE, starting_balance=size,
        current_balance=balance, current_equity=balance,
        highest_end_of_day_balance=balance, highest_equity=balance,
        prior_end_of_day_balance=balance, daily_pnl=D("0"),
        total_profit=D("5000"), realized_pnl=D("5000"), withdrawals=D("0"),
        contracts_open=0, contracts_traded=0, trading_days=5,
        exposures=(ExposurePosition("MNQ", 10),),
        session_id="session-1", daily_pnl_session_id="session-1",
        prior_session_blocked=False, session_ends_at=NOW + timedelta(hours=8),
        payout_cycle=payout_cycle(size), activity_window_days=30,
        qualifying_activity_days=2, activity_day_profit_threshold=D("50"),
        prior_account_failed=False,
    )
    values.update(changes)
    return AccountSnapshot(**values)


def test_standard_matrix_keeps_current_products_and_platforms_distinct():
    profiles = standard_apex_profiles()
    assert len(profiles) == 32
    assert {profile.account_size for profile in profiles} == set(SIZES)
    assert len({profile.config_hash for profile in profiles}) == 32
    assert {profile.stage for profile in profiles} == {
        AccountStage.EVALUATION, AccountStage.PERFORMANCE,
    }


@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("factory,kind", [
    (eod_evaluation_profile, "eod"),
    (intraday_evaluation_profile, "intraday"),
])
def test_current_evaluation_size_matrix_is_verified(factory, kind, size):
    profile = factory(size)
    assert profile.source_review.status == SourceStatus.CURRENT_VERIFIED
    assert profile.profit_target == PROFIT_TARGETS[size]
    assert profile.drawdown.maximum_loss == MAXIMUM_DRAWDOWNS[size]
    assert profile.contract_limit.weighted_exposure.maximum_units == EVALUATION_MAXIMUM_UNITS[size]
    result = evaluate_account_v2(
        profile, evaluation_snapshot(size, kind=kind), require_current_sources=True
    )
    assert result.account_valid and result.trading_allowed_now
    assert result.stage_objective_met


def test_eod_evaluation_dll_blocks_session_without_failing_account():
    size = D("50000")
    profile = eod_evaluation_profile(size)
    snapshot = evaluation_snapshot(size, daily_pnl=-EVALUATION_DAILY_LOSSES[size])
    result = evaluate_account_v2(profile, snapshot)
    assert result.account_valid and not result.account_failed
    assert not result.trading_allowed_now
    assert outcome(result, "daily_loss").status == RuleStatus.SESSION_BLOCKED


def test_intraday_evaluation_has_no_daily_loss_limit():
    profile = intraday_evaluation_profile(D("50000"))
    result = evaluate_account_v2(
        profile, evaluation_snapshot(kind="intraday", daily_pnl=D("-99999"))
    )
    assert outcome(result, "daily_loss").status == RuleStatus.NOT_APPLICABLE
    assert result.account_valid and result.trading_allowed_now


def test_evaluation_contract_ratio_and_breach_are_fail_closed():
    profile = eod_evaluation_profile(D("25000"))
    boundary = evaluate_account_v2(
        profile,
        evaluation_snapshot(D("25000"), exposures=(
            ExposurePosition("NQ", 3), ExposurePosition("MNQ", 10),
        )),
    )
    assert boundary.metric("weighted_exposure_total") == D("4")
    assert outcome(boundary, "contracts").status == RuleStatus.PASS
    breach = evaluate_account_v2(
        profile,
        evaluation_snapshot(D("25000"), exposures=(ExposurePosition("MNQ", 41),)),
    )
    assert breach.account_valid and not breach.trading_allowed_now
    assert outcome(breach, "contracts").status == RuleStatus.TRADING_BLOCKED


def test_evaluation_platform_controls_drawdown_floor_cap():
    size = D("50000")
    rithmic = eod_evaluation_profile(size, platform="rithmic")
    tradovate = eod_evaluation_profile(size, platform="tradovate")
    snapshot = evaluation_snapshot(
        size, current_balance=D("56000"), current_equity=D("56000"),
        highest_end_of_day_balance=D("56000"), total_profit=D("6000"),
    )
    assert evaluate_account_v2(rithmic, snapshot).metric("effective_drawdown_floor") == D("53000")
    assert evaluate_account_v2(tradovate, snapshot).metric("effective_drawdown_floor") == D("54000")


def test_evaluation_access_expires_at_thirty_day_boundary():
    profile = eod_evaluation_profile(D("50000"))
    result = evaluate_account_v2(
        profile, evaluation_snapshot(account_started_at=NOW - timedelta(days=30))
    )
    assert result.account_failed and not result.trading_allowed_now
    assert outcome(result, "access_period").reason == "ACCOUNT_ACCESS_PERIOD_EXPIRED"


def test_performance_scaling_uses_prior_eod_balance_for_contracts_and_dll():
    size = D("100000")
    profile = eod_performance_profile(size)
    snapshot = performance_snapshot(
        size, prior_end_of_day_balance=D("105000"),
        exposures=(ExposurePosition("MNQ", 61),), daily_pnl=D("-2500"),
        payout_cycle=payout_cycle(
            size, qualifying_day_profit_threshold=EOD_QUALIFYING_DAY[size]
        ),
    )
    result = evaluate_account_v2(profile, snapshot, require_current_sources=True)
    assert result.metric("active_scaling_tier") == "L4"
    assert result.metric("active_maximum_units") == D("6")
    assert result.metric("active_daily_loss_limit") == D("2500")
    assert outcome(result, "contracts").status == RuleStatus.TRADING_BLOCKED
    assert outcome(result, "daily_loss").status == RuleStatus.SESSION_BLOCKED
    assert not result.account_failed


@pytest.mark.parametrize("size", (D("25000"), D("100000"), D("150000")))
@pytest.mark.parametrize("factory,kind", [
    (eod_performance_profile, "eod"),
    (intraday_performance_profile, "intraday"),
])
def test_nonconflicting_performance_matrix_is_verified(factory, kind, size):
    profile = factory(size)
    result = evaluate_account_v2(
        profile, performance_snapshot(size, kind=kind), require_current_sources=True
    )
    assert profile.source_review.status == SourceStatus.CURRENT_VERIFIED
    assert result.account_valid and result.trading_allowed_now
    assert outcome(result, "scaling").status == RuleStatus.PASS


def test_performance_scaling_never_descends_below_level_one():
    profile = eod_performance_profile(D("25000"))
    result = evaluate_account_v2(
        profile, performance_snapshot(prior_end_of_day_balance=D("24000"))
    )
    assert result.metric("active_scaling_tier") == "L1"
    assert result.metric("active_maximum_units") == D(SCALING_TIERS[D("25000")][0][2])


@pytest.mark.parametrize("factory", [eod_performance_profile, intraday_performance_profile])
def test_50k_performance_conflict_blocks_account_fail_closed(factory):
    profile = factory(D("50000"))
    assert profile.source_review.status == SourceStatus.SOURCE_CONFLICT
    result = evaluate_account_v2(profile, performance_snapshot(D("50000")))
    assert not result.account_valid and not result.trading_allowed_now
    assert "SOURCE_CONFLICT" in result.blocking_reasons


def test_performance_inactivity_breach_fails_account():
    profile = eod_performance_profile(D("25000"))
    result = evaluate_account_v2(
        profile, performance_snapshot(qualifying_activity_days=1)
    )
    assert result.account_failed and not result.trading_allowed_now
    assert outcome(result, "inactivity").reason == "INACTIVITY_REQUIREMENT_BREACHED"


def test_performance_inactivity_requires_exact_window_evidence():
    profile = eod_performance_profile(D("25000"))
    result = evaluate_account_v2(profile, performance_snapshot(activity_window_days=29))
    assert not result.account_valid and not result.trading_allowed_now
    assert outcome(result, "inactivity").reason == "ACTIVITY_WINDOW_MISMATCH"


def test_payout_requires_five_qualifying_days_at_profile_threshold():
    profile = eod_performance_profile(D("25000"))
    insufficient = evaluate_payout_v2(
        profile,
        performance_snapshot(payout_cycle=payout_cycle(qualifying_days_since_last_payout=4)),
        PayoutRequest(D("500")),
    )
    assert "PAYOUT_CYCLE_QUALIFYING_DAYS_NOT_MET" in insufficient.blocking_reasons
    mismatch = evaluate_payout_v2(
        profile,
        performance_snapshot(payout_cycle=payout_cycle(qualifying_day_profit_threshold=D("99"))),
        PayoutRequest(D("500")),
    )
    assert "CYCLE_QUALIFYING_DAY_THRESHOLD_MISMATCH" in mismatch.blocking_reasons


def test_payout_consistency_rejects_exactly_fifty_percent():
    profile = eod_performance_profile(D("25000"))
    exact = payout_cycle(best_day_profit_since_last_payout=D("2500"))
    result = evaluate_payout_v2(
        profile, performance_snapshot(payout_cycle=exact), PayoutRequest(D("500"))
    )
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" in result.blocking_reasons


def test_payout_cap_safety_net_and_six_payout_limit():
    size = D("25000")
    profile = eod_performance_profile(size)
    at_cap = evaluate_payout_v2(
        profile, performance_snapshot(size), PayoutRequest(D(EOD_PAYOUT_CAPS[size][0]))
    )
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" not in at_cap.blocking_reasons
    over_cap = evaluate_payout_v2(
        profile, performance_snapshot(size), PayoutRequest(D("1000.01"))
    )
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" in over_cap.blocking_reasons
    safety_net = evaluate_payout_v2(
        profile,
        performance_snapshot(size, current_balance=D("26599.99"), current_equity=D("26599.99")),
        PayoutRequest(D("500")),
    )
    assert "PAYOUT_MINIMUM_BALANCE_NOT_MET" in safety_net.blocking_reasons
    exhausted = evaluate_payout_v2(
        profile,
        performance_snapshot(size, payout_cycle=payout_cycle(payout_count=6)),
        PayoutRequest(D("500")),
    )
    assert "PAYOUT_COUNT_LIMIT_REACHED" in exhausted.blocking_reasons


@pytest.mark.parametrize("factory,thresholds,caps", [
    (eod_performance_profile, EOD_QUALIFYING_DAY, EOD_PAYOUT_CAPS),
    (intraday_performance_profile, INTRADAY_QUALIFYING_DAY, INTRADAY_PAYOUT_CAPS),
])
@pytest.mark.parametrize("size", SIZES)
def test_performance_payout_matrix_matches_product_route(factory, thresholds, caps, size):
    profile = factory(size)
    assert profile.payout.minimum_qualifying_day_profit == thresholds[size]
    assert tuple(tier.maximum_amount for tier in profile.payout.tiers) == tuple(
        D(value) for value in caps[size]
    )
    assert profile.payout.maximum_payout_count == 6


def test_legacy_products_are_explicitly_separate_and_unimplemented():
    support = {item.program_id: item for item in APEX_PROGRAM_SUPPORT}
    assert support["eod_performance"].source_status == SourceStatus.SOURCE_CONFLICT
    assert support["intraday_performance"].source_status == SourceStatus.SOURCE_CONFLICT
    legacy = support["legacy_products"]
    assert legacy.stage == AccountStage.UNKNOWN
    assert legacy.source_status == SourceStatus.INCOMPLETE
    assert not legacy.implemented
    assert "LEGACY" in legacy.reason
