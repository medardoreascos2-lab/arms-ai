"""Pure prop-firm rule calculations. No execution or account mutation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from .models_v1 import (
    AccountSnapshot, AccountStage, ConsistencyApplication, ConsistencyMode, DailyLossEnforcement, DrawdownModel, PayoutRequest,
    PropFirmProfile, ResetBoundary, RuleEvaluationResult, ValueBasis,
)


@dataclass(frozen=True)
class DrawdownEvaluation:
    drawdown_floor: Decimal | None
    remaining_drawdown: Decimal | None
    breached: bool
    reason: str | None


@dataclass(frozen=True)
class DailyLossEvaluation:
    daily_loss_limit: Decimal | None
    daily_loss_used: Decimal | None
    daily_loss_remaining: Decimal | None
    breached: bool
    reason: str | None


@dataclass(frozen=True)
class ContractLimitEvaluation:
    maximum_contracts: int
    current_contracts: int | None
    remaining_contract_capacity: int | None
    breached: bool
    reason: str | None


@dataclass(frozen=True)
class ConsistencyEvaluation:
    best_day_fraction: Decimal | None
    profit_basis: Decimal | None
    breached: bool
    reason: str | None


def _value(snapshot: AccountSnapshot, basis: ValueBasis) -> Decimal | None:
    return snapshot.current_balance if basis == ValueBasis.BALANCE else snapshot.current_equity


def evaluate_drawdown(profile: PropFirmProfile, snapshot: AccountSnapshot) -> DrawdownEvaluation:
    policy = profile.drawdown
    if policy.transition is not None or policy.reference_update_mode is not None or policy.breach_basis == ValueBasis.MIN_BALANCE_OR_EQUITY:
        return DrawdownEvaluation(None, None, True, "UNSUPPORTED_POLICY_USE_V2")
    if policy.model == DrawdownModel.NONE:
        return DrawdownEvaluation(None, None, False, None)
    if snapshot.starting_balance is None:
        return DrawdownEvaluation(None, None, True, "MISSING_STARTING_BALANCE")
    if snapshot.starting_balance != profile.starting_balance:
        return DrawdownEvaluation(None, None, True, "STARTING_BALANCE_MISMATCH")

    if policy.model == DrawdownModel.TRAILING_INTRADAY:
        high = snapshot.highest_equity
        if high is None:
            return DrawdownEvaluation(None, None, True, "MISSING_HIGH_WATER_MARK")
        if high < snapshot.starting_balance:
            return DrawdownEvaluation(None, None, True, "INVALID_HIGH_WATER_MARK")
        basis = policy.breach_basis
        if snapshot.current_equity is not None and high < snapshot.current_equity:
            return DrawdownEvaluation(None, None, True, "INVALID_HIGH_WATER_MARK")
    elif policy.model == DrawdownModel.TRAILING_END_OF_DAY:
        high = snapshot.highest_end_of_day_balance
        if high is None:
            return DrawdownEvaluation(None, None, True, "MISSING_END_OF_DAY_HIGH_WATER_MARK")
        if high < snapshot.starting_balance:
            return DrawdownEvaluation(None, None, True, "INVALID_END_OF_DAY_HIGH_WATER_MARK")
        basis = policy.breach_basis
    else:
        high = snapshot.starting_balance
        basis = (ValueBasis.BALANCE if policy.model == DrawdownModel.BALANCE_BASED
                 else ValueBasis.EQUITY if policy.model == DrawdownModel.EQUITY_BASED
                 else policy.breach_basis)

    observed = _value(snapshot, basis)
    if observed is None:
        code = "MISSING_CURRENT_BALANCE" if basis == ValueBasis.BALANCE else "MISSING_CURRENT_EQUITY"
        return DrawdownEvaluation(None, None, True, code)
    floor = high - policy.maximum_loss
    if policy.floor_cap is not None:
        floor = min(floor, policy.floor_cap)
    remaining = observed - floor
    return DrawdownEvaluation(floor, remaining, remaining <= 0,
                              "DRAWDOWN_LIMIT_BREACHED" if remaining <= 0 else None)


def evaluate_daily_loss(profile: PropFirmProfile, snapshot: AccountSnapshot) -> DailyLossEvaluation:
    limit = profile.daily_loss.limit
    if profile.daily_loss.enforcement != DailyLossEnforcement.ACCOUNT_FAIL:
        return DailyLossEvaluation(limit, None, None, True, "UNSUPPORTED_POLICY_USE_V2")
    if limit is None:
        return DailyLossEvaluation(None, None, None, False, None)
    if snapshot.daily_pnl is None:
        return DailyLossEvaluation(limit, None, None, True, "MISSING_DAILY_PNL")
    used = max(Decimal("0"), -snapshot.daily_pnl)
    remaining = limit - used
    return DailyLossEvaluation(limit, used, remaining, remaining <= 0,
                               "DAILY_LOSS_LIMIT_BREACHED" if remaining <= 0 else None)


def evaluate_contract_limit(profile: PropFirmProfile, snapshot: AccountSnapshot) -> ContractLimitEvaluation:
    maximum = profile.contract_limit.maximum_open
    if profile.contract_limit.weighted_exposure is not None or maximum is None:
        return ContractLimitEvaluation(maximum or 0, None, None, True, "UNSUPPORTED_POLICY_USE_V2")
    if snapshot.contracts_open is None:
        return ContractLimitEvaluation(maximum, None, None, True, "MISSING_CONTRACTS_OPEN")
    remaining = maximum - snapshot.contracts_open
    if remaining < 0:
        return ContractLimitEvaluation(maximum, snapshot.contracts_open, remaining, True,
                                       "OPEN_CONTRACT_LIMIT_BREACHED")
    traded_cap = profile.contract_limit.maximum_traded
    if traded_cap is not None:
        if snapshot.contracts_traded is None:
            return ContractLimitEvaluation(maximum, snapshot.contracts_open, remaining, True,
                                           "MISSING_CONTRACTS_TRADED")
        if snapshot.contracts_traded > traded_cap:
            return ContractLimitEvaluation(maximum, snapshot.contracts_open, remaining, True,
                                           "TRADED_CONTRACT_LIMIT_BREACHED")
    return ContractLimitEvaluation(maximum, snapshot.contracts_open, remaining, False, None)


def evaluate_consistency(profile: PropFirmProfile, snapshot: AccountSnapshot) -> ConsistencyEvaluation:
    policy = profile.consistency
    if policy.application != ConsistencyApplication.STAGE:
        return ConsistencyEvaluation(None, None, True, "UNSUPPORTED_POLICY_USE_V2")
    if not policy.enabled:
        return ConsistencyEvaluation(None, None, False, None)
    if snapshot.best_day_profit is None:
        return ConsistencyEvaluation(None, None, True, "MISSING_BEST_DAY_PROFIT")
    basis = (snapshot.total_profit if policy.calculation_mode == ConsistencyMode.TOTAL_PROFIT
             else snapshot.realized_pnl)
    if basis is None:
        code = ("MISSING_TOTAL_PROFIT" if policy.calculation_mode == ConsistencyMode.TOTAL_PROFIT
                else "MISSING_REALIZED_PNL")
        return ConsistencyEvaluation(None, None, True, code)
    if basis <= 0 or basis < policy.minimum_profit_basis:
        return ConsistencyEvaluation(None, basis, True, "INSUFFICIENT_CONSISTENCY_PROFIT_BASIS")
    if snapshot.best_day_profit < 0:
        return ConsistencyEvaluation(None, basis, True, "INVALID_BEST_DAY_PROFIT")
    fraction = snapshot.best_day_profit / basis
    return ConsistencyEvaluation(fraction, basis,
                                 fraction > policy.maximum_best_day_fraction,
                                 "CONSISTENCY_LIMIT_BREACHED" if fraction > policy.maximum_best_day_fraction
                                 else None)


def _profile_reasons(profile: PropFirmProfile, snapshot: AccountSnapshot) -> list[str]:
    reasons: list[str] = []
    if snapshot.stage is None:
        reasons.append("MISSING_ACCOUNT_STAGE")
    elif snapshot.stage == AccountStage.UNKNOWN or profile.stage == AccountStage.UNKNOWN:
        reasons.append("UNKNOWN_ACCOUNT_STAGE")
    elif snapshot.stage != profile.stage:
        reasons.append("ACCOUNT_STAGE_MISMATCH")
    if snapshot.as_of is None:
        reasons.append("MISSING_SNAPSHOT_TIME")
    elif snapshot.as_of < profile.effective_from or (
        profile.effective_to is not None and snapshot.as_of >= profile.effective_to
    ):
        reasons.append("PROFILE_NOT_EFFECTIVE")
    if snapshot.starting_balance is None:
        reasons.append("MISSING_STARTING_BALANCE")
    elif snapshot.starting_balance != profile.starting_balance:
        reasons.append("STARTING_BALANCE_MISMATCH")
    if snapshot.current_balance is None:
        reasons.append("MISSING_CURRENT_BALANCE")
    if snapshot.current_equity is None:
        reasons.append("MISSING_CURRENT_EQUITY")
    return reasons


def _result(profile: PropFirmProfile, reasons: list[str], metrics: dict,
            warnings: tuple[str, ...] = ()) -> RuleEvaluationResult:
    unique = tuple(dict.fromkeys(reasons))
    return RuleEvaluationResult(not unique, unique, warnings,
                                tuple(sorted(metrics.items())), profile.identity, profile.version)


def _requires_v2(profile: PropFirmProfile) -> bool:
    payout = profile.payout
    return bool(
        profile.allow_zero_starting_balance or profile.source_review is not None
        or profile.drawdown.transition is not None
        or profile.drawdown.reference_update_mode is not None
        or profile.drawdown.breach_basis == ValueBasis.MIN_BALANCE_OR_EQUITY
        or profile.daily_loss.enforcement != DailyLossEnforcement.ACCOUNT_FAIL
        or profile.daily_loss.reset_boundary != ResetBoundary.SESSION_END
        or profile.consistency.application != ConsistencyApplication.STAGE
        or profile.contract_limit.weighted_exposure is not None
        or profile.contract_limit.maximum_open is None
        or payout.minimum_winning_days_per_cycle or payout.minimum_trading_days_per_cycle
        or payout.minimum_profit_since_last_payout is not None
        or payout.minimum_payout_amount is not None
        or payout.maximum_fraction_basis.value != "AVAILABLE_PROFIT"
        or payout.tiers or payout.consistency_per_cycle
        or not payout.require_session_clear
    )


def evaluate_account(profile: PropFirmProfile, snapshot: AccountSnapshot) -> RuleEvaluationResult:
    """Assess configured account rules and stage completion. This grants no trade authority."""
    if _requires_v2(profile):
        return _result(profile, ["UNSUPPORTED_POLICY_USE_V2"], {})
    reasons = _profile_reasons(profile, snapshot)
    metrics: dict = {}
    drawdown = evaluate_drawdown(profile, snapshot)
    daily = evaluate_daily_loss(profile, snapshot)
    contracts = evaluate_contract_limit(profile, snapshot)
    consistency = evaluate_consistency(profile, snapshot)
    for evaluation in (drawdown, daily, contracts, consistency):
        if evaluation.reason:
            reasons.append(evaluation.reason)
    metrics.update(
        drawdown_floor=drawdown.drawdown_floor,
        remaining_drawdown=drawdown.remaining_drawdown,
        daily_loss_limit=daily.daily_loss_limit,
        daily_loss_used=daily.daily_loss_used,
        daily_loss_remaining=daily.daily_loss_remaining,
        maximum_contracts=contracts.maximum_contracts,
        current_contracts=contracts.current_contracts,
        remaining_contract_capacity=contracts.remaining_contract_capacity,
        best_day_fraction=consistency.best_day_fraction,
        consistency_profit_basis=consistency.profit_basis,
    )
    if profile.trading_days.minimum_days:
        if snapshot.trading_days is None:
            reasons.append("MISSING_TRADING_DAYS")
        elif snapshot.trading_days < profile.trading_days.minimum_days:
            reasons.append("MINIMUM_TRADING_DAYS_NOT_MET")
    if profile.profit_target is not None:
        if snapshot.total_profit is None:
            reasons.append("MISSING_TOTAL_PROFIT")
        else:
            remaining = profile.profit_target - snapshot.total_profit
            metrics["profit_target_remaining"] = remaining
            if remaining > 0:
                reasons.append("PROFIT_TARGET_NOT_MET")
    return _result(profile, reasons, metrics)


def evaluate_payout(
    profile: PropFirmProfile, snapshot: AccountSnapshot, request: PayoutRequest
) -> RuleEvaluationResult:
    """Assess payout conditions without changing balances or recording a payout."""
    policy = profile.payout
    if _requires_v2(profile):
        return _result(profile, ["UNSUPPORTED_POLICY_USE_V2"], {})
    account = evaluate_account(profile, snapshot)
    reasons = list(account.blocking_reasons)
    metrics = dict(account.metrics)
    metrics["requested_payout"] = request.amount
    if not policy.enabled:
        reasons.append("PAYOUT_DISABLED")
        return _result(profile, reasons, metrics)

    if policy.minimum_trading_days:
        if snapshot.trading_days is None:
            reasons.append("MISSING_TRADING_DAYS")
        elif snapshot.trading_days < policy.minimum_trading_days:
            reasons.append("PAYOUT_MINIMUM_TRADING_DAYS_NOT_MET")
    if snapshot.withdrawals is None:
        reasons.append("MISSING_WITHDRAWALS")
    elif snapshot.withdrawals < 0:
        reasons.append("INVALID_WITHDRAWALS")
    if snapshot.total_profit is None:
        reasons.append("MISSING_TOTAL_PROFIT")
    elif snapshot.withdrawals is not None:
        available_profit = snapshot.total_profit - snapshot.withdrawals
        metrics["available_profit"] = available_profit
        if available_profit <= 0 or request.amount > available_profit:
            reasons.append("PAYOUT_EXCEEDS_AVAILABLE_PROFIT")
        if policy.minimum_profit is not None and available_profit < policy.minimum_profit:
            reasons.append("PAYOUT_MINIMUM_PROFIT_NOT_MET")
        if (policy.maximum_payout_fraction is not None
                and request.amount > available_profit * policy.maximum_payout_fraction):
            reasons.append("PAYOUT_FRACTION_LIMIT_BREACHED")
    if policy.maximum_payout_amount is not None and request.amount > policy.maximum_payout_amount:
        reasons.append("PAYOUT_AMOUNT_LIMIT_BREACHED")
    if snapshot.current_balance is None:
        reasons.append("MISSING_CURRENT_BALANCE")
    else:
        after = snapshot.current_balance - request.amount
        metrics["post_payout_balance"] = after
        if policy.minimum_balance is not None and after < policy.minimum_balance:
            reasons.append("PAYOUT_MINIMUM_BALANCE_NOT_MET")
        if policy.minimum_buffer is not None:
            floor = metrics["drawdown_floor"]
            if floor is None:
                reasons.append("MISSING_DRAWDOWN_FLOOR")
            else:
                basis = (ValueBasis.BALANCE if profile.drawdown.model == DrawdownModel.BALANCE_BASED
                         else ValueBasis.EQUITY if profile.drawdown.model == DrawdownModel.EQUITY_BASED
                         else profile.drawdown.breach_basis)
                observed = _value(snapshot, basis)
                if observed is None:
                    reasons.append("MISSING_PAYOUT_BUFFER_BASIS")
                else:
                    buffer = observed - request.amount - floor
                    metrics["post_payout_buffer"] = buffer
                    if buffer < policy.minimum_buffer:
                        reasons.append("PAYOUT_MINIMUM_BUFFER_NOT_MET")
    if policy.consistency_required:
        if not profile.consistency.enabled:
            reasons.append("PAYOUT_CONSISTENCY_POLICY_MISSING")
        else:
            consistency = evaluate_consistency(profile, snapshot)
            if consistency.reason:
                reasons.append(consistency.reason)
    if policy.minimum_days_since_prior_payout:
        if snapshot.prior_payout_count is None:
            reasons.append("MISSING_PRIOR_PAYOUT_COUNT")
        elif snapshot.prior_payout_count > 0:
            if snapshot.last_payout_at is None:
                reasons.append("MISSING_LAST_PAYOUT_TIME")
            elif snapshot.as_of is None:
                reasons.append("MISSING_SNAPSHOT_TIME")
            elif snapshot.last_payout_at > snapshot.as_of:
                reasons.append("INVALID_LAST_PAYOUT_TIME")
            elif snapshot.as_of - snapshot.last_payout_at < timedelta(
                days=policy.minimum_days_since_prior_payout
            ):
                reasons.append("PAYOUT_COOLDOWN_NOT_MET")
    return _result(profile, reasons, metrics)
