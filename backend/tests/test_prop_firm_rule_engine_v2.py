"""Generic R24B1 extension matrix. Values here are synthetic, never firm rules."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountSnapshot, AccountStage, ConsistencyApplication, ConsistencyMode, ConsistencyPolicy,
    ContractLimitEnforcement, ContractLimitPolicy, DailyLossEnforcement, DailyLossPolicy, DrawdownModel,
    DrawdownPolicy, DrawdownTransition, ExposurePosition, ExposureWeight, InstrumentGroup,
    PayoutCycleSnapshot, PayoutFractionBasis, PayoutPolicy, PayoutRequest, PayoutTier,
    PropFirmProfile, ReferenceUpdateMode, ResetBoundary, RuleStatus, ScalingPolicy, ScalingTier,
    SourceEvidence, SourceReview,
    SourceStatus, TradingDayPolicy, ValueBasis, WeightedExposurePolicy,
    evaluate_account, evaluate_account_v2, evaluate_drawdown_v2, evaluate_payout_v2,
)


NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def profile(**changes):
    data = dict(
        firm_id="synthetic", program_id="generic", stage=AccountStage.EVALUATION,
        version="v2", effective_from=NOW - timedelta(days=30),
        account_size=D("50000"), starting_balance=D("50000"),
        drawdown=DrawdownPolicy(DrawdownModel.STATIC, D("2000"), ValueBasis.EQUITY),
        daily_loss=DailyLossPolicy(D("500")),
        contract_limit=ContractLimitPolicy(5),
        consistency=ConsistencyPolicy(False), payout=PayoutPolicy(False),
    )
    data.update(changes)
    return PropFirmProfile(**data)


def cycle(**changes):
    data = dict(cycle_id="cycle-1", payout_count=0, current_cycle_start=NOW-timedelta(days=10),
                withdrawals_total=D("0"), profit_since_last_payout=D("1000"),
                winning_days_since_last_payout=5, trading_days_since_last_payout=7,
                best_day_profit_since_last_payout=D("200"))
    data.update(changes)
    return PayoutCycleSnapshot(**data)


def snapshot(**changes):
    data = dict(as_of=NOW, stage=AccountStage.EVALUATION, starting_balance=D("50000"),
                current_balance=D("51000"), current_equity=D("50900"),
                daily_pnl=D("100"), total_profit=D("1000"), realized_pnl=D("1000"),
                best_day_profit=D("200"), withdrawals=D("0"), contracts_open=2,
                contracts_traded=2, trading_days=7, highest_equity=D("51500"),
                highest_end_of_day_balance=D("51000"),
                session_id="s2", daily_pnl_session_id="s2",
                session_ends_at=NOW+timedelta(hours=3), payout_cycle=cycle(),
                prior_account_failed=False, prior_session_blocked=False)
    data.update(changes)
    return AccountSnapshot(**data)


def status(result, rule):
    return next(o.status for o in result.outcomes if o.rule_id == rule)


def test_temporary_session_block_does_not_fail_account_and_resets_on_new_session():
    p = profile(daily_loss=DailyLossPolicy(D("500"), DailyLossEnforcement.SESSION_BLOCK))
    blocked = evaluate_account_v2(p, snapshot(daily_pnl=D("-500")))
    assert blocked.account_valid and not blocked.account_failed
    assert not blocked.trading_allowed_now and blocked.stage_objective_met
    assert status(blocked, "daily_loss") == RuleStatus.SESSION_BLOCKED
    assert next(o for o in blocked.outcomes if o.rule_id == "daily_loss").reset_at == NOW+timedelta(hours=3)
    next_session = snapshot(daily_pnl=D("0"), session_id="s3", daily_pnl_session_id="s3")
    assert evaluate_account_v2(p, next_session).trading_allowed_now


def test_traded_contract_limit_preserves_reason_and_blocks_without_account_failure():
    p = profile(contract_limit=ContractLimitPolicy(
        5, maximum_traded=10,
        breach_enforcement=ContractLimitEnforcement.TRADING_BLOCK,
    ))
    result = evaluate_account_v2(p, snapshot(contracts_open=2, contracts_traded=11))
    assert result.account_valid and not result.account_failed
    assert not result.trading_allowed_now
    contract = next(o for o in result.outcomes if o.rule_id == "contracts")
    assert contract.status == RuleStatus.TRADING_BLOCKED
    assert contract.reason == "TRADED_CONTRACT_LIMIT_BREACHED"


def test_session_pnl_mismatch_fails_closed():
    p = profile(daily_loss=DailyLossPolicy(D("500"), DailyLossEnforcement.SESSION_BLOCK))
    result = evaluate_account_v2(p, snapshot(daily_pnl_session_id="old"))
    assert result.account_valid and not result.trading_allowed_now
    assert "DAILY_PNL_SESSION_MISMATCH" in result.blocking_reasons


def test_hard_account_failure_is_distinct():
    result = evaluate_account_v2(profile(), snapshot(current_equity=D("48000")))
    assert result.account_failed and not result.account_valid
    assert not result.trading_allowed_now
    assert status(result, "drawdown") == RuleStatus.ACCOUNT_FAILED
    assert result.failure_reasons == ("DRAWDOWN_LIMIT_BREACHED",)


def test_objective_pending_is_not_account_failure():
    p = profile(trading_days=TradingDayPolicy(10), profit_target=D("2000"))
    result = evaluate_account_v2(p, snapshot())
    assert result.account_valid and result.trading_allowed_now
    assert not result.stage_objective_met
    assert status(result, "trading_days") == RuleStatus.OBJECTIVE_PENDING
    assert status(result, "profit_target") == RuleStatus.OBJECTIVE_PENDING


@pytest.mark.parametrize("consequence,expected,stage_met,trading", [
    (DailyLossEnforcement.WARNING_ONLY, RuleStatus.WARNING, True, True),
    (DailyLossEnforcement.OBJECTIVE_ONLY, RuleStatus.OBJECTIVE_PENDING, False, True),
    (DailyLossEnforcement.ACCOUNT_FAIL, RuleStatus.ACCOUNT_FAILED, False, False),
])
def test_daily_loss_enforcement(consequence, expected, stage_met, trading):
    p = profile(daily_loss=DailyLossPolicy(D("500"), consequence))
    result = evaluate_account_v2(p, snapshot(daily_pnl=D("-501")))
    assert status(result, "daily_loss") == expected
    assert result.stage_objective_met == stage_met
    assert result.trading_allowed_now == trading
    if consequence == DailyLossEnforcement.WARNING_ONLY:
        assert result.warnings == ("DAILY_LOSS_LIMIT_BREACHED",)


def test_explicit_not_applicable_daily_loss():
    p = profile(daily_loss=DailyLossPolicy(None, DailyLossEnforcement.NOT_APPLICABLE))
    assert status(evaluate_account_v2(p, snapshot()), "daily_loss") == RuleStatus.NOT_APPLICABLE


def test_zero_start_balance_is_explicit_and_negative_rejected():
    with pytest.raises(ValueError):
        profile(starting_balance=D("0"))
    p = profile(starting_balance=D("0"), allow_zero_starting_balance=True)
    result = evaluate_drawdown_v2(p, snapshot(
        starting_balance=D("0"), current_balance=D("100"), current_equity=D("100")
    ))
    assert result.effective_drawdown_floor == D("-2000")
    assert not result.breached
    with pytest.raises(ValueError):
        profile(starting_balance=D("-1"), allow_zero_starting_balance=True)


def test_drawdown_transition_pre_post_and_fixed_floor():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, D("2000"), ValueBasis.EQUITY,
        transition=DrawdownTransition(post_event_payout_count=1, post_event_fixed_floor=D("50000"))
    ))
    before = evaluate_drawdown_v2(p, snapshot(
        payout_cycle=cycle(payout_count=0), highest_end_of_day_balance=D("51000")
    ))
    after = evaluate_drawdown_v2(p, snapshot(
        payout_cycle=cycle(payout_count=1), highest_end_of_day_balance=D("51000")
    ))
    assert (before.effective_drawdown_floor, before.drawdown_model_phase) == (
        D("49000"), "END_OF_DAY_BALANCE"
    )
    assert (after.effective_drawdown_floor, after.drawdown_model_phase) == (
        D("50000"), "POST_EVENT_FIXED"
    )


def test_floor_cap_and_lock_are_distinct():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, D("2000"), ValueBasis.EQUITY,
        floor_cap=D("50000"), transition=DrawdownTransition(floor_lock=True)
    ))
    result = evaluate_drawdown_v2(p, snapshot(
        highest_end_of_day_balance=D("54000"), prior_drawdown_floor=D("50500")
    ))
    assert result.effective_drawdown_floor == D("50500")
    assert result.drawdown_model_phase.endswith("_LOCKED")
    missing = evaluate_drawdown_v2(p, snapshot(prior_drawdown_floor=None))
    assert missing.outcome.status == RuleStatus.INCOMPLETE_DATA


def test_eod_reference_with_intraday_equity_breach():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, D("2000"), ValueBasis.EQUITY,
        reference_update_mode=ReferenceUpdateMode.END_OF_DAY_BALANCE
    ))
    result = evaluate_drawdown_v2(p, snapshot(
        highest_end_of_day_balance=D("52000"),
        current_balance=D("51000"), current_equity=D("50000")
    ))
    assert result.effective_drawdown_floor == D("50000")
    assert result.breached


def test_minimum_balance_or_equity_breach_basis():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.STATIC, D("2000"), ValueBasis.MIN_BALANCE_OR_EQUITY
    ))
    assert evaluate_drawdown_v2(p, snapshot(
        current_balance=D("51000"), current_equity=D("47999")
    )).breached


def weighted_profile():
    return profile(contract_limit=ContractLimitPolicy(
        None, weighted_exposure=WeightedExposurePolicy(
            D("5"),
            instrument_weights=(ExposureWeight("special-micro", D("0.2")),),
            product_group_weights=(ExposureWeight("mini", D("1")),
                                   ExposureWeight("micro", D("0.1"))),
            instrument_groups=(InstrumentGroup("regular-mini", "mini"),
                               InstrumentGroup("regular-micro", "micro"),
                               InstrumentGroup("special-micro", "micro")),
        )
    ))


def test_weighted_exposure_and_instrument_override():
    p = weighted_profile()
    result = evaluate_account_v2(p, snapshot(
        contracts_open=None,
        exposures=(ExposurePosition("regular-mini", 2, "mini"),
                   ExposurePosition("regular-micro", 20, "micro"),
                   ExposurePosition("special-micro", 5, "micro"))
    ))
    assert result.metric("weighted_exposure_total") == D("5")
    assert result.metric("remaining_exposure_capacity") == D("0")
    assert result.account_valid


def test_weighted_exposure_breach_and_unknown_mapping():
    p = weighted_profile()
    breach = evaluate_account_v2(p, snapshot(
        contracts_open=None, exposures=(ExposurePosition("regular-mini", 6, "mini"),)
    ))
    assert breach.account_failed
    assert "WEIGHTED_EXPOSURE_LIMIT_BREACHED" in breach.failure_reasons
    unknown = evaluate_account_v2(p, snapshot(
        contracts_open=None, exposures=(ExposurePosition("unknown", 1),)
    ))
    assert not unknown.trading_allowed_now
    assert "UNSUPPORTED_EXPOSURE_MAPPING" in unknown.blocking_reasons
    spoofed = evaluate_account_v2(p, snapshot(
        contracts_open=None, exposures=(ExposurePosition("unknown", 1, "mini"),)
    ))
    assert "UNSUPPORTED_EXPOSURE_MAPPING" in spoofed.blocking_reasons
    mismatched = evaluate_account_v2(p, snapshot(
        contracts_open=None, exposures=(ExposurePosition("regular-mini", 1, "micro"),)
    ))
    assert "EXPOSURE_GROUP_MISMATCH" in mismatched.blocking_reasons


def test_legacy_evaluator_rejects_v2_policy():
    p = weighted_profile()
    legacy = evaluate_account(p, snapshot(contracts_open=None, exposures=()))
    assert not legacy.eligible
    assert legacy.blocking_reasons == ("UNSUPPORTED_POLICY_USE_V2",)


def payout_profile(**changes):
    config = dict(enabled=True, minimum_winning_days_per_cycle=5,
                  minimum_trading_days_per_cycle=3, minimum_profit_since_last_payout=D("100"),
                  minimum_buffer=D("1000"), maximum_payout_amount=D("600"),
                  maximum_payout_fraction=D("0.5"))
    config.update(changes)
    return profile(payout=PayoutPolicy(**config))


def test_payout_cycle_days_and_winning_days():
    p = payout_profile()
    result = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        winning_days_since_last_payout=4, trading_days_since_last_payout=2
    )), PayoutRequest(D("200")))
    assert not result.payout_eligible and result.account_valid
    assert {"PAYOUT_CYCLE_WINNING_DAYS_NOT_MET", "PAYOUT_CYCLE_TRADING_DAYS_NOT_MET"} <= set(result.blocking_reasons)


def test_payout_profit_balance_buffer_and_fixed_cap():
    p = payout_profile(minimum_buffer=D("2801"), maximum_payout_amount=D("300"),
                       minimum_balance=D("50700"))
    result = evaluate_payout_v2(p, snapshot(), PayoutRequest(D("400")))
    assert {"PAYOUT_AMOUNT_LIMIT_BREACHED", "PAYOUT_MINIMUM_BUFFER_NOT_MET",
            "PAYOUT_MINIMUM_BALANCE_NOT_MET"} <= set(result.blocking_reasons)
    assert result.metric("post_payout_buffer") == D("2500")


def test_payout_fraction_uses_configured_balance_basis():
    p = payout_profile(maximum_fraction_basis=PayoutFractionBasis.CURRENT_BALANCE,
                       maximum_payout_fraction=D("0.01"))
    assert evaluate_payout_v2(p, snapshot(), PayoutRequest(D("500"))).payout_eligible
    assert "PAYOUT_FRACTION_LIMIT_BREACHED" in evaluate_payout_v2(
        p, snapshot(), PayoutRequest(D("600"))
    ).blocking_reasons


def test_payout_wait_and_tier_by_prior_payout_count():
    p = payout_profile(minimum_days_since_prior_payout=7,
                       tiers=(PayoutTier(0, maximum_amount=D("300")),
                              PayoutTier(1, maximum_amount=D("600"))))
    first = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(payout_count=0)),
                               PayoutRequest(D("400")))
    assert "PAYOUT_AMOUNT_LIMIT_BREACHED" in first.blocking_reasons
    second = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        payout_count=1, last_payout_at=NOW-timedelta(days=3)
    )), PayoutRequest(D("400")))
    assert "PAYOUT_COOLDOWN_NOT_MET" in second.blocking_reasons
    ready = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        payout_count=1, last_payout_at=NOW-timedelta(days=8)
    )), PayoutRequest(D("400")))
    assert ready.payout_eligible


def test_payout_cycle_consistency_and_missing_data():
    p = profile(
        consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT,
                                      ConsistencyApplication.PAYOUT_CYCLE),
        payout=PayoutPolicy(True, consistency_per_cycle=True),
    )
    failed = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        best_day_profit_since_last_payout=D("400")
    )), PayoutRequest(D("200")))
    assert "PAYOUT_CYCLE_CONSISTENCY_NOT_MET" in failed.blocking_reasons
    missing = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        best_day_profit_since_last_payout=None
    )), PayoutRequest(D("200")))
    assert "MISSING_CYCLE_CONSISTENCY_DATA" in missing.blocking_reasons


def test_missing_cycle_is_not_approvable():
    p = payout_profile()
    result = evaluate_payout_v2(p, snapshot(payout_cycle=None), PayoutRequest(D("200")))
    assert not result.payout_eligible
    assert "MISSING_PAYOUT_CYCLE" in result.blocking_reasons


def test_payout_evaluator_does_not_mutate_cycle_or_account():
    p = payout_profile()
    s = snapshot()
    before = s
    result = evaluate_payout_v2(p, s, PayoutRequest(D("200")))
    assert result.payout_eligible and s == before


def source_review(status=SourceStatus.CURRENT_VERIFIED, due=NOW+timedelta(days=1)):
    reviewed = NOW - timedelta(days=2)
    evidence = SourceEvidence("https://example.invalid/rules", "Synthetic rules", reviewed,
                              rule_heading="Rule A", normalized_source_hash="abc")
    return SourceReview(status, reviewed, (evidence,), due)


def test_source_current_stale_conflict_and_missing():
    current = profile(source_review=source_review())
    assert evaluate_account_v2(current, snapshot(), require_current_sources=True).account_valid
    stale = profile(source_review=source_review(due=NOW-timedelta(days=1)))
    result = evaluate_account_v2(stale, snapshot(), require_current_sources=True)
    assert not result.account_valid and result.source_status == SourceStatus.STALE_REVIEW_REQUIRED
    conflict = profile(source_review=source_review(SourceStatus.SOURCE_CONFLICT))
    assert not evaluate_account_v2(conflict, snapshot(), require_current_sources=True).account_valid
    assert "MISSING_SOURCE_REVIEW" in evaluate_account_v2(
        profile(), snapshot(), require_current_sources=True
    ).blocking_reasons


def test_source_status_does_not_change_automatically_without_due_date():
    review = source_review(due=None)
    assert review.status_at(NOW+timedelta(days=999)) == SourceStatus.CURRENT_VERIFIED


def test_profile_hash_covers_all_extension_semantics():
    p = profile()
    variants = (
        replace(p, daily_loss=DailyLossPolicy(D("500"), DailyLossEnforcement.SESSION_BLOCK)),
        replace(p, drawdown=replace(p.drawdown, transition=DrawdownTransition(floor_lock=True))),
        replace(p, contract_limit=weighted_profile().contract_limit),
        replace(p, payout=PayoutPolicy(True, minimum_winning_days_per_cycle=5)),
        replace(p, source_review=source_review()),
        replace(p, allow_zero_starting_balance=True),
    )
    assert all(v.config_hash != p.config_hash for v in variants)
    assert len({v.config_hash for v in variants}) == len(variants)


def test_invalid_extension_configuration_rejected():
    with pytest.raises(ValueError):
        DrawdownTransition(post_event_payout_count=1)
    with pytest.raises(ValueError):
        WeightedExposurePolicy(D("5"))
    with pytest.raises(ValueError):
        PayoutPolicy(True, tiers=(PayoutTier(1, maximum_amount=D("100")),
                                  PayoutTier(0, maximum_amount=D("100"))))
    scaling = ScalingPolicy((ScalingTier("L1", D("0"), D("2"), D("500")),))
    with pytest.raises(ValueError):
        profile(scaling=scaling)
    with pytest.raises(ValueError):
        profile(
            scaling=scaling,
            contract_limit=ContractLimitPolicy(
                None, weighted_exposure=WeightedExposurePolicy(
                    D("1"), (ExposureWeight("NQ", D("1")),)
                ),
            ),
        )


def test_scaling_missing_prior_eod_balance_blocks_dynamic_limits():
    p = profile(
        scaling=ScalingPolicy((ScalingTier("L1", D("0"), D("2"), D("500")),)),
        contract_limit=ContractLimitPolicy(
            None, weighted_exposure=WeightedExposurePolicy(
                D("2"), (ExposureWeight("NQ", D("1")),)
            ),
            breach_enforcement=ContractLimitEnforcement.TRADING_BLOCK,
        ),
    )
    result = evaluate_account_v2(
        p, snapshot(exposures=(ExposurePosition("NQ", 1),), prior_end_of_day_balance=None)
    )
    assert not result.trading_allowed_now
    assert status(result, "scaling") == RuleStatus.INCOMPLETE_DATA
    assert "MISSING_PRIOR_END_OF_DAY_BALANCE" in result.blocking_reasons



def test_cycle_only_consistency_does_not_block_stage_objective():
    p = profile(
        consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT,
                                      ConsistencyApplication.PAYOUT_CYCLE),
        payout=PayoutPolicy(True, consistency_per_cycle=True),
    )
    s = snapshot(best_day_profit=D("800"), payout_cycle=cycle())
    account = evaluate_account_v2(p, s)
    payout = evaluate_payout_v2(p, s, PayoutRequest(D("200")))
    assert account.stage_objective_met and payout.payout_eligible
    assert status(account, "consistency") == RuleStatus.NOT_APPLICABLE



def test_session_block_uses_configured_trading_day_boundary():
    p = profile(daily_loss=DailyLossPolicy(
        D("500"), DailyLossEnforcement.SESSION_BLOCK, ResetBoundary.TRADING_DAY_END
    ))
    s = snapshot(daily_pnl=D("-500"), trading_day_ends_at=NOW+timedelta(hours=5))
    outcome = next(o for o in evaluate_account_v2(p, s).outcomes if o.rule_id == "daily_loss")
    assert outcome.status == RuleStatus.SESSION_BLOCKED
    assert outcome.reset_at == NOW+timedelta(hours=5)
    missing = evaluate_account_v2(p, snapshot(daily_pnl=D("-500"), trading_day_ends_at=None))
    assert "MISSING_SESSION_CONTEXT" in missing.blocking_reasons



def test_source_conflict_fails_closed_even_without_current_source_requirement():
    p = profile(source_review=source_review(SourceStatus.SOURCE_CONFLICT))
    result = evaluate_account_v2(p, snapshot())
    assert not result.account_valid
    assert "SOURCE_CONFLICT" in result.blocking_reasons


def test_payout_cannot_pass_with_incomplete_trading_data_even_when_session_clear_not_required():
    p = payout_profile(require_session_clear=False)
    result = evaluate_payout_v2(p, snapshot(contracts_open=None), PayoutRequest(D("200")))
    assert not result.payout_eligible
    assert "MISSING_CONTRACTS_OPEN" in result.blocking_reasons


def test_transition_requires_identified_cycle_and_invalid_cycle_best_day_blocks_payout():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.STATIC, D("2000"), ValueBasis.EQUITY,
        transition=DrawdownTransition(post_event_payout_count=1, post_event_fixed_floor=D("50000"))
    ))
    result = evaluate_drawdown_v2(p, snapshot(payout_cycle=cycle(cycle_id=None)))
    assert result.outcome.status == RuleStatus.INCOMPLETE_DATA
    payout_p = profile(
        consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT,
                                      ConsistencyApplication.PAYOUT_CYCLE),
        payout=PayoutPolicy(True, consistency_per_cycle=True),
    )
    payout = evaluate_payout_v2(payout_p, snapshot(payout_cycle=cycle(
        best_day_profit_since_last_payout=D("-1")
    )), PayoutRequest(D("200")))
    assert not payout.payout_eligible
    assert "INVALID_CYCLE_BEST_DAY_PROFIT" in payout.blocking_reasons



def test_prior_hard_failure_remains_failed_after_balance_recovers():
    p = profile()
    recovered = evaluate_account_v2(p, snapshot(prior_account_failed=True))
    assert recovered.account_failed and not recovered.account_valid
    assert "PRIOR_ACCOUNT_FAILURE" in recovered.failure_reasons
    missing = evaluate_account_v2(p, snapshot(prior_account_failed=None))
    assert not missing.account_valid and not missing.account_failed
    assert "MISSING_PRIOR_ACCOUNT_FAILURE_STATE" in missing.blocking_reasons



def test_source_review_rejects_impossible_chronology():
    evidence = SourceEvidence("https://example.invalid/rules", "Synthetic", NOW)
    with pytest.raises(ValueError):
        SourceReview(SourceStatus.CURRENT_VERIFIED, NOW-timedelta(days=1), (evidence,))
    with pytest.raises(ValueError):
        SourceReview(SourceStatus.CURRENT_VERIFIED, NOW, (evidence,), NOW-timedelta(days=1))



def test_prior_session_block_persists_until_session_changes():
    p = profile(daily_loss=DailyLossPolicy(D("500"), DailyLossEnforcement.SESSION_BLOCK))
    still_blocked = evaluate_account_v2(p, snapshot(
        daily_pnl=D("0"), prior_session_blocked=True, blocked_session_id="s2"
    ))
    assert still_blocked.account_valid and not still_blocked.trading_allowed_now
    assert "PRIOR_SESSION_BLOCK_ACTIVE" in still_blocked.blocking_reasons
    next_session = evaluate_account_v2(p, snapshot(
        daily_pnl=D("0"), prior_session_blocked=True, blocked_session_id="s1"
    ))
    assert next_session.trading_allowed_now
    unknown = evaluate_account_v2(p, snapshot(prior_session_blocked=None))
    assert "MISSING_PRIOR_SESSION_BLOCK_STATE" in unknown.blocking_reasons



def test_consistency_can_apply_to_both_stage_and_cycle():
    p = profile(
        consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT,
                                      ConsistencyApplication.BOTH),
        payout=PayoutPolicy(True, consistency_per_cycle=True),
    )
    s = snapshot(best_day_profit=D("400"), payout_cycle=cycle(
        best_day_profit_since_last_payout=D("200")
    ))
    account = evaluate_account_v2(p, s)
    payout = evaluate_payout_v2(p, s, PayoutRequest(D("200")))
    assert not account.stage_objective_met
    assert "CONSISTENCY_LIMIT_BREACHED" in account.blocking_reasons
    assert not payout.payout_eligible


def test_minimum_payout_amount_and_tier_specific_cycle_requirements():
    p = profile(payout=PayoutPolicy(
        True, minimum_payout_amount=D("125"),
        tiers=(PayoutTier(0, maximum_amount=D("500")),
               PayoutTier(1, maximum_amount=D("600"),
                          minimum_winning_days_per_cycle=6,
                          minimum_profit_since_last_payout=D("300"))),
    ))
    small = evaluate_payout_v2(p, snapshot(), PayoutRequest(D("124")))
    assert "PAYOUT_MINIMUM_AMOUNT_NOT_MET" in small.blocking_reasons
    second = evaluate_payout_v2(p, snapshot(payout_cycle=cycle(
        payout_count=1, winning_days_since_last_payout=5,
        profit_since_last_payout=D("200")
    )), PayoutRequest(D("200")))
    assert {"PAYOUT_TIER_WINNING_DAYS_NOT_MET", "PAYOUT_TIER_PROFIT_NOT_MET"} <= set(second.blocking_reasons)



def test_invalid_boolean_and_cycle_identity_rejected():
    with pytest.raises(ValueError):
        profile(allow_zero_starting_balance=1)
    with pytest.raises(ValueError):
        PayoutCycleSnapshot(cycle_id=17)
    with pytest.raises(ValueError):
        PayoutPolicy(True, require_session_clear=1)
