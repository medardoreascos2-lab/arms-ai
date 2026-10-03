"""Focused domain tests using synthetic profiles only; no broker or PAPER adapter."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountProgram, AccountSnapshot, AccountStage, ConsistencyMode, ConsistencyPolicy,
    ContractLimitPolicy, DailyLossPolicy, DrawdownModel, DrawdownPolicy, PayoutPolicy,
    PayoutRequest, PropFirmProfile, TradingDayPolicy, ValueBasis, evaluate_account,
    evaluate_consistency, evaluate_contract_limit, evaluate_daily_loss, evaluate_drawdown,
    evaluate_payout,
)


NOW = datetime(2026, 1, 15, tzinfo=timezone.utc)


def profile(**changes):
    defaults = dict(
        firm_id="synthetic", program_id="generic", stage=AccountStage.EVALUATION,
        version="1", effective_from=NOW - timedelta(days=30),
        account_size=D("50000"), starting_balance=D("50000"),
        drawdown=DrawdownPolicy(DrawdownModel.STATIC, D("2000"), ValueBasis.EQUITY),
        daily_loss=DailyLossPolicy(D("500")),
        contract_limit=ContractLimitPolicy(5),
        consistency=ConsistencyPolicy(False),
        payout=PayoutPolicy(False),
    )
    defaults.update(changes)
    return PropFirmProfile(**defaults)


def snapshot(**changes):
    defaults = dict(
        as_of=NOW, stage=AccountStage.EVALUATION, starting_balance=D("50000"),
        current_balance=D("51000"), current_equity=D("50900"),
        realized_pnl=D("1000"), unrealized_pnl=D("-100"), daily_pnl=D("100"),
        highest_balance=D("51200"), highest_equity=D("51100"),
        highest_end_of_day_balance=D("51000"), contracts_open=2,
        contracts_traded=3, trading_days=10, best_day_profit=D("200"),
        total_profit=D("1000"), withdrawals=D("0"), prior_payout_count=0,
    )
    defaults.update(changes)
    return AccountSnapshot(**defaults)


def test_static_drawdown_floor_and_equality_breach():
    p = profile()
    result = evaluate_drawdown(p, snapshot(current_equity=D("48000")))
    assert (result.drawdown_floor, result.remaining_drawdown, result.breached) == (
        D("48000"), D("0"), True
    )
    assert result.reason == "DRAWDOWN_LIMIT_BREACHED"


def test_intraday_trailing_uses_equity_high_and_cap():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_INTRADAY, D("2000"), ValueBasis.EQUITY, D("50000")
    ))
    result = evaluate_drawdown(p, snapshot(highest_equity=D("53000"), current_equity=D("50500")))
    assert (result.drawdown_floor, result.remaining_drawdown, result.breached) == (
        D("50000"), D("500"), False
    )


def test_end_of_day_trailing_uses_closed_day_balance_high():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, D("2000"), ValueBasis.BALANCE
    ))
    result = evaluate_drawdown(p, snapshot(
        highest_end_of_day_balance=D("52000"), highest_equity=D("55000"),
        current_balance=D("50000")
    ))
    assert result.drawdown_floor == D("50000")
    assert result.breached


@pytest.mark.parametrize("model,basis,observed", [
    (DrawdownModel.BALANCE_BASED, None, "current_balance"),
    (DrawdownModel.EQUITY_BASED, None, "current_equity"),
    (DrawdownModel.STATIC, ValueBasis.BALANCE, "current_balance"),
])
def test_fixed_drawdown_basis(model, basis, observed):
    p = profile(drawdown=DrawdownPolicy(model, D("2000"), basis))
    s = snapshot(**{observed: D("48001")})
    assert evaluate_drawdown(p, s).remaining_drawdown == D("1")


def test_drawdown_none_is_explicitly_disabled():
    p = profile(drawdown=DrawdownPolicy(DrawdownModel.NONE))
    assert evaluate_drawdown(p, snapshot()).breached is False


@pytest.mark.parametrize("missing,reason", [
    ({"highest_equity": None}, "MISSING_HIGH_WATER_MARK"),
    ({"current_equity": None}, "MISSING_CURRENT_EQUITY"),
    ({"starting_balance": None}, "MISSING_STARTING_BALANCE"),
    ({"highest_equity": D("50000"), "current_equity": D("50900")}, "INVALID_HIGH_WATER_MARK"),
])
def test_drawdown_missing_or_inconsistent_data_blocks(missing, reason):
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_INTRADAY, D("2000"), ValueBasis.EQUITY
    ))
    result = evaluate_drawdown(p, snapshot(**missing))
    assert result.breached and result.reason == reason


def test_daily_loss_calculation_and_missing_data():
    p = profile()
    result = evaluate_daily_loss(p, snapshot(daily_pnl=D("-350")))
    assert (result.daily_loss_used, result.daily_loss_remaining, result.breached) == (
        D("350"), D("150"), False
    )
    assert evaluate_daily_loss(p, snapshot(daily_pnl=D("-500"))).breached
    assert evaluate_daily_loss(p, snapshot(daily_pnl=None)).reason == "MISSING_DAILY_PNL"


def test_contract_open_and_traded_caps():
    p = profile(contract_limit=ContractLimitPolicy(5, 10))
    assert evaluate_contract_limit(p, snapshot(contracts_open=5)).remaining_contract_capacity == 0
    assert evaluate_contract_limit(p, snapshot(contracts_open=6)).reason == "OPEN_CONTRACT_LIMIT_BREACHED"
    assert evaluate_contract_limit(p, snapshot(contracts_traded=11)).reason == "TRADED_CONTRACT_LIMIT_BREACHED"
    assert evaluate_contract_limit(p, snapshot(contracts_traded=None)).reason == "MISSING_CONTRACTS_TRADED"


def test_consistency_fraction_and_denominator_fail_closed():
    p = profile(consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT))
    assert evaluate_consistency(p, snapshot()).best_day_fraction == D("0.2")
    assert evaluate_consistency(p, snapshot(best_day_profit=D("400"))).breached
    assert evaluate_consistency(p, snapshot(total_profit=None)).reason == "MISSING_TOTAL_PROFIT"
    assert evaluate_consistency(p, snapshot(total_profit=D("0"))).breached
    assert evaluate_consistency(p, snapshot(total_profit=D("50"))).breached


def test_consistency_realized_basis_is_configured_explicitly():
    p = profile(consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.REALIZED_PNL))
    assert evaluate_consistency(p, snapshot(realized_pnl=D("1000"), total_profit=D("500"))).best_day_fraction == D("0.2")
    assert evaluate_consistency(p, snapshot(realized_pnl=None)).reason == "MISSING_REALIZED_PNL"


def test_profile_hash_changes_with_rule_and_is_immutable():
    p = profile()
    modified = replace(p, daily_loss=DailyLossPolicy(D("400")))
    assert p.config_hash != modified.config_hash
    assert p.identity != modified.identity
    with pytest.raises(FrozenInstanceError):
        p.version = "2"


def test_program_selects_stage_and_size_and_fails_ambiguous():
    evaluation = profile()
    funded = profile(stage=AccountStage.FUNDED, account_size=D("50000"))
    smaller = profile(account_size=D("25000"), starting_balance=D("25000"))
    program = AccountProgram("synthetic", "generic", (evaluation, funded, smaller))
    assert program.select(D("50000"), AccountStage.FUNDED, NOW) is funded
    assert program.select(D("25000"), AccountStage.EVALUATION, NOW) is smaller
    with pytest.raises(ValueError):
        program.select(D("100000"), AccountStage.EVALUATION, NOW)


def test_stage_specific_rule_and_snapshot_mismatch_blocks():
    funded = profile(stage=AccountStage.FUNDED, contract_limit=ContractLimitPolicy(2))
    result = evaluate_account(funded, snapshot(stage=AccountStage.FUNDED, contracts_open=3))
    assert "OPEN_CONTRACT_LIMIT_BREACHED" in result.blocking_reasons
    assert "ACCOUNT_STAGE_MISMATCH" in evaluate_account(funded, snapshot()).blocking_reasons


def test_account_stage_completion_and_missing_fields_fail_closed():
    p = profile(trading_days=TradingDayPolicy(8), profit_target=D("2000"))
    result = evaluate_account(p, snapshot(total_profit=None, trading_days=None, daily_pnl=None))
    assert not result.eligible
    assert {"MISSING_TOTAL_PROFIT", "MISSING_TRADING_DAYS", "MISSING_DAILY_PNL"} <= set(result.blocking_reasons)
    assert "PROFIT_TARGET_NOT_MET" in evaluate_account(p, snapshot()).blocking_reasons
    assert evaluate_account(p, snapshot(total_profit=D("2000"))).eligible


def test_payout_requirements_and_no_mutation():
    p = profile(payout=PayoutPolicy(
        True, minimum_trading_days=8, minimum_buffer=D("1000"),
        minimum_balance=D("50000"), minimum_profit=D("500"),
        maximum_payout_amount=D("600"), maximum_payout_fraction=D("0.5"),
        minimum_days_since_prior_payout=7
    ))
    s = snapshot(prior_payout_count=1, last_payout_at=NOW - timedelta(days=8))
    before = s
    result = evaluate_payout(p, s, PayoutRequest(D("400")))
    assert result.eligible
    assert result.metric("post_payout_balance") == D("50600")
    assert s == before
    assert evaluate_payout(p, s, PayoutRequest(D("601"))).eligible is False


def test_payout_each_gate_and_missing_values():
    p = profile(payout=PayoutPolicy(
        True, minimum_trading_days=12, minimum_buffer=D("900"),
        minimum_balance=D("51000"), minimum_profit=D("1200"),
        maximum_payout_amount=D("300"), maximum_payout_fraction=D("0.2"),
        minimum_days_since_prior_payout=7,
    ))
    result = evaluate_payout(p, snapshot(
        prior_payout_count=1, last_payout_at=NOW - timedelta(days=2)
    ), PayoutRequest(D("400")))
    assert {
        "PAYOUT_MINIMUM_TRADING_DAYS_NOT_MET", "PAYOUT_MINIMUM_BALANCE_NOT_MET",
        "PAYOUT_MINIMUM_PROFIT_NOT_MET", "PAYOUT_AMOUNT_LIMIT_BREACHED",
        "PAYOUT_FRACTION_LIMIT_BREACHED", "PAYOUT_COOLDOWN_NOT_MET",
    } <= set(result.blocking_reasons)
    missing = evaluate_payout(p, snapshot(
        trading_days=None, withdrawals=None, total_profit=None,
        prior_payout_count=None, current_balance=None
    ), PayoutRequest(D("100")))
    assert not missing.eligible
    assert {"MISSING_TRADING_DAYS", "MISSING_WITHDRAWALS", "MISSING_TOTAL_PROFIT",
            "MISSING_PRIOR_PAYOUT_COUNT", "MISSING_CURRENT_BALANCE"} <= set(missing.blocking_reasons)


def test_payout_buffer_and_consistency_requirement():
    p = profile(
        consistency=ConsistencyPolicy(True, D("0.3"), D("100"), ConsistencyMode.TOTAL_PROFIT),
        payout=PayoutPolicy(True, minimum_buffer=D("2901"), consistency_required=True),
    )
    result = evaluate_payout(p, snapshot(best_day_profit=D("400")), PayoutRequest(D("100")))
    assert "CONSISTENCY_LIMIT_BREACHED" in result.blocking_reasons
    assert "PAYOUT_MINIMUM_BUFFER_NOT_MET" in result.blocking_reasons


def test_disabled_payout_and_unknown_stage_block():
    p = profile()
    assert "PAYOUT_DISABLED" in evaluate_payout(p, snapshot(), PayoutRequest(D("100"))).blocking_reasons
    assert "UNKNOWN_ACCOUNT_STAGE" in evaluate_account(
        p, snapshot(stage=AccountStage.UNKNOWN)
    ).blocking_reasons


def test_invalid_configuration_and_snapshot_are_rejected():
    with pytest.raises(ValueError):
        DailyLossPolicy(D("-1"))
    with pytest.raises(ValueError):
        ConsistencyPolicy(True, D("1.1"), D("100"), ConsistencyMode.TOTAL_PROFIT)
    with pytest.raises(ValueError):
        PayoutRequest(D("0"))
    with pytest.raises(ValueError):
        PayoutRequest(None)
    with pytest.raises(ValueError):
        profile(account_size=None)
    with pytest.raises(ValueError):
        AccountSnapshot(current_balance=float("nan"))
    with pytest.raises(ValueError):
        profile(effective_from=datetime(2026, 1, 1))



def test_profile_effective_window_and_ambiguous_selection_fail_closed():
    first = profile(effective_to=NOW + timedelta(days=1))
    overlapping = profile(version="2", effective_from=NOW - timedelta(days=1), effective_to=NOW + timedelta(days=3))
    program = AccountProgram("synthetic", "generic", (first, overlapping))
    with pytest.raises(ValueError):
        program.select(D("50000"), AccountStage.EVALUATION, NOW)
    with pytest.raises(ValueError):
        program.select(D("50000"), AccountStage.EVALUATION, NOW + timedelta(days=40))
    with pytest.raises(ValueError):
        program.select(50000.0, AccountStage.EVALUATION, NOW)
    assert "PROFILE_NOT_EFFECTIVE" in evaluate_account(
        first, snapshot(as_of=NOW + timedelta(days=2))
    ).blocking_reasons


def test_trailing_end_of_day_missing_high_fails_closed():
    p = profile(drawdown=DrawdownPolicy(
        DrawdownModel.TRAILING_END_OF_DAY, D("2000"), ValueBasis.BALANCE
    ))
    assert evaluate_drawdown(p, snapshot(
        highest_end_of_day_balance=None
    )).reason == "MISSING_END_OF_DAY_HIGH_WATER_MARK"
    assert evaluate_drawdown(p, snapshot(
        highest_end_of_day_balance=D("49000")
    )).reason == "INVALID_END_OF_DAY_HIGH_WATER_MARK"


def test_payout_buffer_uses_drawdown_basis():
    payout = PayoutPolicy(True, minimum_buffer=D("2850"))
    equity_profile = profile(payout=payout)
    balance_profile = profile(
        drawdown=DrawdownPolicy(DrawdownModel.STATIC, D("2000"), ValueBasis.BALANCE),
        payout=payout,
    )
    s = snapshot()
    equity_result = evaluate_payout(equity_profile, s, PayoutRequest(D("100")))
    balance_result = evaluate_payout(balance_profile, s, PayoutRequest(D("100")))
    assert equity_result.metric("post_payout_buffer") == D("2800")
    assert not equity_result.eligible
    assert balance_result.metric("post_payout_buffer") == D("2900")
    assert balance_result.eligible


def test_profile_hash_covers_source_and_effective_dates():
    p = profile()
    assert p.config_hash != replace(p, source_reference="verified-source").config_hash
    assert p.config_hash != replace(p, effective_to=NOW + timedelta(days=1)).config_hash


def test_negative_payout_minimum_is_invalid():
    with pytest.raises(ValueError):
        PayoutPolicy(True, minimum_buffer=D("-1"))
