"""Context-aware, pure rule evaluation with independent account, session, stage and payout outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from .models_v1 import (
    AccountSnapshot, AccountStage, ConsistencyApplication, ConsistencyMode, DailyLossEnforcement, DrawdownModel,
    ContractLimitEnforcement, PayoutFractionBasis, PayoutRequest, PropFirmProfile, ReferenceUpdateMode, ResetBoundary,
    SourceStatus, ValueBasis,
)
from .rule_engine_v1 import evaluate_consistency


class RuleStatus(str, Enum):
    PASS = "PASS"
    SESSION_BLOCKED = "SESSION_BLOCKED"
    TRADING_BLOCKED = "TRADING_BLOCKED"
    ACCOUNT_FAILED = "ACCOUNT_FAILED"
    OBJECTIVE_PENDING = "OBJECTIVE_PENDING"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


class RuleScope(str, Enum):
    ACCOUNT = "ACCOUNT"
    TRADING = "TRADING"
    STAGE = "STAGE"
    PAYOUT = "PAYOUT"


@dataclass(frozen=True)
class RuleOutcome:
    rule_id: str
    scope: RuleScope
    status: RuleStatus
    reason: str
    evidence: tuple[tuple[str, Decimal | int | str | bool | None], ...] = ()
    reset_at: datetime | None = None


@dataclass(frozen=True)
class DrawdownResultV2:
    effective_drawdown_floor: Decimal | None
    drawdown_model_phase: str
    remaining_drawdown: Decimal | None
    breached: bool
    outcome: RuleOutcome


@dataclass(frozen=True)
class AccountEvaluationV2:
    account_valid: bool
    account_failed: bool
    trading_allowed_now: bool
    stage_objective_met: bool
    payout_eligible: bool
    outcomes: tuple[RuleOutcome, ...]
    warnings: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    failure_reasons: tuple[str, ...]
    metrics: tuple[tuple[str, Decimal | int | str | bool | None], ...]
    profile_identity: str
    rule_version: str
    source_status: SourceStatus | None

    def metric(self, name: str) -> Decimal | int | str | bool | None:
        return dict(self.metrics).get(name)


def _out(rule: str, scope: RuleScope, status: RuleStatus, reason: str,
         **evidence: Decimal | int | str | bool | None) -> RuleOutcome:
    return RuleOutcome(rule, scope, status, reason, tuple(sorted(evidence.items())))


def _observed(snapshot: AccountSnapshot, basis: ValueBasis | None) -> Decimal | None:
    if basis == ValueBasis.BALANCE:
        return snapshot.current_balance
    if basis == ValueBasis.EQUITY:
        return snapshot.current_equity
    if basis == ValueBasis.MIN_BALANCE_OR_EQUITY:
        if snapshot.current_balance is None or snapshot.current_equity is None:
            return None
        return min(snapshot.current_balance, snapshot.current_equity)
    return None


def _reference_mode(profile: PropFirmProfile) -> ReferenceUpdateMode:
    policy = profile.drawdown
    if policy.reference_update_mode is not None:
        return policy.reference_update_mode
    if policy.model == DrawdownModel.TRAILING_INTRADAY:
        return ReferenceUpdateMode.INTRADAY_EQUITY
    if policy.model == DrawdownModel.TRAILING_END_OF_DAY:
        return ReferenceUpdateMode.END_OF_DAY_BALANCE
    return ReferenceUpdateMode.FIXED_START


def _breach_basis(profile: PropFirmProfile) -> ValueBasis | None:
    model = profile.drawdown.model
    if model == DrawdownModel.BALANCE_BASED:
        return ValueBasis.BALANCE
    if model == DrawdownModel.EQUITY_BASED:
        return ValueBasis.EQUITY
    return profile.drawdown.breach_basis


def evaluate_drawdown_v2(profile: PropFirmProfile, snapshot: AccountSnapshot) -> DrawdownResultV2:
    policy = profile.drawdown
    if policy.model == DrawdownModel.NONE:
        return DrawdownResultV2(None, "DISABLED", None, False,
                                _out("drawdown", RuleScope.ACCOUNT, RuleStatus.NOT_APPLICABLE,
                                     "DRAWDOWN_NOT_APPLICABLE"))
    def incomplete(reason: str, phase: str = "UNKNOWN") -> DrawdownResultV2:
        return DrawdownResultV2(None, phase, None, False,
                                _out("drawdown", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA, reason))
    if snapshot.starting_balance is None:
        return incomplete("MISSING_STARTING_BALANCE")
    if snapshot.starting_balance != profile.starting_balance:
        return incomplete("STARTING_BALANCE_MISMATCH")
    mode = _reference_mode(profile)
    if mode == ReferenceUpdateMode.INTRADAY_EQUITY:
        high = snapshot.highest_equity
        if high is None:
            return incomplete("MISSING_HIGH_WATER_MARK")
        if high < snapshot.starting_balance or (
            snapshot.current_equity is not None and high < snapshot.current_equity
        ):
            return incomplete("INVALID_HIGH_WATER_MARK")
    elif mode == ReferenceUpdateMode.END_OF_DAY_BALANCE:
        high = snapshot.highest_end_of_day_balance
        if high is None:
            return incomplete("MISSING_END_OF_DAY_HIGH_WATER_MARK")
        if high < snapshot.starting_balance:
            return incomplete("INVALID_END_OF_DAY_HIGH_WATER_MARK")
    else:
        high = snapshot.starting_balance
    basis = _breach_basis(profile)
    observed = _observed(snapshot, basis)
    if observed is None:
        return incomplete("MISSING_DRAWDOWN_BREACH_BASIS")
    floor = high - policy.maximum_loss
    if policy.floor_cap is not None:
        floor = min(floor, policy.floor_cap)
    phase = mode.value
    transition = policy.transition
    if transition is not None:
        if transition.post_event_payout_count is not None:
            cycle = snapshot.payout_cycle
            if (cycle is None or cycle.payout_count is None or not cycle.cycle_id
                    or cycle.current_cycle_start is None):
                return incomplete("MISSING_PAYOUT_COUNT_FOR_DRAWDOWN")
            if cycle.payout_count >= transition.post_event_payout_count:
                floor = transition.post_event_fixed_floor
                phase = "POST_EVENT_FIXED"
        if transition.floor_lock:
            if snapshot.prior_drawdown_floor is None:
                return incomplete("MISSING_PRIOR_DRAWDOWN_FLOOR")
            floor = max(floor, snapshot.prior_drawdown_floor)
            phase += "_LOCKED"
    remaining = observed - floor
    breached = remaining <= 0
    outcome = _out("drawdown", RuleScope.ACCOUNT,
                   RuleStatus.ACCOUNT_FAILED if breached else RuleStatus.PASS,
                   "DRAWDOWN_LIMIT_BREACHED" if breached else "DRAWDOWN_PASS",
                   floor=floor, observed=observed, phase=phase)
    return DrawdownResultV2(floor, phase, remaining, breached, outcome)


def _daily_outcome(
    profile: PropFirmProfile, snapshot: AccountSnapshot,
    limit_override: Decimal | None = None,
) -> RuleOutcome:
    policy = profile.daily_loss
    limit = limit_override if limit_override is not None else policy.limit
    if limit is None:
        return _out("daily_loss", RuleScope.TRADING, RuleStatus.NOT_APPLICABLE,
                    "DAILY_LOSS_NOT_APPLICABLE")
    if snapshot.daily_pnl is None:
        return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_DAILY_PNL")
    if policy.enforcement == DailyLossEnforcement.SESSION_BLOCK:
        boundary = (snapshot.session_ends_at if policy.reset_boundary == ResetBoundary.SESSION_END
                    else snapshot.trading_day_ends_at)
        if not snapshot.session_id or not snapshot.daily_pnl_session_id or boundary is None:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "MISSING_SESSION_CONTEXT")
        if snapshot.daily_pnl_session_id != snapshot.session_id:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "DAILY_PNL_SESSION_MISMATCH")
        if snapshot.as_of is None or boundary <= snapshot.as_of:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "INVALID_SESSION_BOUNDARY")
        if snapshot.prior_session_blocked is None:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "MISSING_PRIOR_SESSION_BLOCK_STATE")
        if snapshot.prior_session_blocked and not snapshot.blocked_session_id:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "MISSING_BLOCKED_SESSION_ID")
        if not snapshot.prior_session_blocked and snapshot.blocked_session_id is not None:
            return _out("daily_loss", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "INCONSISTENT_SESSION_BLOCK_STATE")
        if snapshot.prior_session_blocked and snapshot.blocked_session_id == snapshot.session_id:
            return RuleOutcome("daily_loss", RuleScope.TRADING, RuleStatus.SESSION_BLOCKED,
                               "PRIOR_SESSION_BLOCK_ACTIVE", (), boundary)
    used = max(Decimal("0"), -snapshot.daily_pnl)
    if used < limit:
        return _out("daily_loss", RuleScope.TRADING, RuleStatus.PASS, "DAILY_LOSS_PASS",
                    used=used, remaining=limit - used)
    mapping = {
        DailyLossEnforcement.SESSION_BLOCK: (RuleScope.TRADING, RuleStatus.SESSION_BLOCKED),
        DailyLossEnforcement.ACCOUNT_FAIL: (RuleScope.ACCOUNT, RuleStatus.ACCOUNT_FAILED),
        DailyLossEnforcement.WARNING_ONLY: (RuleScope.TRADING, RuleStatus.WARNING),
        DailyLossEnforcement.OBJECTIVE_ONLY: (RuleScope.STAGE, RuleStatus.OBJECTIVE_PENDING),
    }
    scope, status = mapping[policy.enforcement]
    outcome = _out("daily_loss", scope, status, "DAILY_LOSS_LIMIT_BREACHED",
                   used=used, remaining=limit - used)
    if status == RuleStatus.SESSION_BLOCKED:
        return RuleOutcome(outcome.rule_id, outcome.scope, outcome.status, outcome.reason,
                           outcome.evidence, boundary)
    return outcome


def _contract_outcome(
    profile: PropFirmProfile, snapshot: AccountSnapshot,
    maximum_units_override: Decimal | None = None,
) -> tuple[RuleOutcome, dict]:
    policy = profile.contract_limit
    metrics: dict = {}
    if policy.unavailable_reason is not None:
        return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                    policy.unavailable_reason), metrics
    breach_reason = None
    if policy.maximum_open is not None:
        if snapshot.contracts_open is None:
            return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "MISSING_CONTRACTS_OPEN"), metrics
        metrics["remaining_contract_capacity"] = policy.maximum_open - snapshot.contracts_open
        if snapshot.contracts_open > policy.maximum_open:
            breach_reason = "OPEN_CONTRACT_LIMIT_BREACHED"
    if policy.maximum_traded is not None:
        if snapshot.contracts_traded is None:
            return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "MISSING_CONTRACTS_TRADED"), metrics
        if snapshot.contracts_traded > policy.maximum_traded:
            breach_reason = breach_reason or "TRADED_CONTRACT_LIMIT_BREACHED"
    weighted = policy.weighted_exposure
    if weighted is None and breach_reason is None:
        return _out("contracts", RuleScope.TRADING, RuleStatus.PASS, "CONTRACT_LIMIT_PASS"), metrics
    if weighted is None:
        return _contract_breach(policy, metrics, breach_reason)
    if snapshot.exposures is None:
        return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_EXPOSURES"), metrics
    instruments = {item.key: item.units_per_contract for item in weighted.instrument_weights}
    groups = {item.key: item.units_per_contract for item in weighted.product_group_weights}
    trusted_groups = {item.instrument: item.product_group for item in weighted.instrument_groups}
    total = Decimal("0")
    for position in snapshot.exposures:
        weight = instruments.get(position.instrument)
        trusted_group = trusted_groups.get(position.instrument)
        if position.product_group is not None and trusted_group is not None and position.product_group != trusted_group:
            return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "EXPOSURE_GROUP_MISMATCH", instrument=position.instrument), metrics
        if weight is None and trusted_group is not None:
            weight = groups.get(trusted_group)
        if weight is None:
            return _out("contracts", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                        "UNSUPPORTED_EXPOSURE_MAPPING", instrument=position.instrument), metrics
        total += weight * position.quantity
    maximum_units = maximum_units_override if maximum_units_override is not None else weighted.maximum_units
    metrics["weighted_exposure_total"] = total
    metrics["remaining_exposure_capacity"] = maximum_units - total
    if total > maximum_units:
        return _contract_breach(policy, metrics, "WEIGHTED_EXPOSURE_LIMIT_BREACHED")
    if breach_reason is not None:
        return _contract_breach(policy, metrics, breach_reason)
    return _out("contracts", RuleScope.TRADING, RuleStatus.PASS, "CONTRACT_LIMIT_PASS"), metrics


def _scaling_outcome(
    profile: PropFirmProfile, snapshot: AccountSnapshot,
) -> tuple[RuleOutcome, Decimal | None, Decimal | None, dict]:
    policy = profile.scaling
    if policy is None:
        return (_out("scaling", RuleScope.TRADING, RuleStatus.NOT_APPLICABLE,
                     "SCALING_NOT_APPLICABLE"), None, None, {})
    if snapshot.prior_end_of_day_balance is None:
        return (_out("scaling", RuleScope.TRADING, RuleStatus.INCOMPLETE_DATA,
                     "MISSING_PRIOR_END_OF_DAY_BALANCE"), None, None, {})
    profit = snapshot.prior_end_of_day_balance - profile.starting_balance
    tier = policy.tiers[0]
    for candidate in policy.tiers:
        if profit >= candidate.minimum_profit:
            tier = candidate
        else:
            break
    metrics = {
        "active_scaling_tier": tier.name,
        "scaling_profit": profit,
        "active_maximum_units": tier.maximum_units,
        "active_daily_loss_limit": tier.daily_loss_limit,
    }
    return (_out("scaling", RuleScope.TRADING, RuleStatus.PASS, "SCALING_TIER_RESOLVED",
                 tier=tier.name, profit=profit), tier.maximum_units, tier.daily_loss_limit, metrics)


def _contract_breach(policy, metrics: dict, reason: str) -> tuple[RuleOutcome, dict]:
    mapping = {
        ContractLimitEnforcement.ACCOUNT_FAIL: (RuleScope.ACCOUNT, RuleStatus.ACCOUNT_FAILED),
        ContractLimitEnforcement.TRADING_BLOCK: (RuleScope.TRADING, RuleStatus.TRADING_BLOCKED),
        ContractLimitEnforcement.WARNING_ONLY: (RuleScope.TRADING, RuleStatus.WARNING),
        ContractLimitEnforcement.OBJECTIVE_ONLY: (RuleScope.STAGE, RuleStatus.OBJECTIVE_PENDING),
    }
    scope, status = mapping[policy.breach_enforcement]
    return _out("contracts", scope, status, reason), metrics


def _access_period_outcome(profile: PropFirmProfile, snapshot: AccountSnapshot) -> RuleOutcome:
    if profile.maximum_access_days is None:
        return _out("access_period", RuleScope.ACCOUNT, RuleStatus.NOT_APPLICABLE,
                    "ACCESS_PERIOD_NOT_APPLICABLE")
    if snapshot.account_started_at is None:
        return _out("access_period", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_ACCOUNT_START_TIME")
    if snapshot.as_of is None:
        return _out("access_period", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_SNAPSHOT_TIME")
    if snapshot.account_started_at > snapshot.as_of:
        return _out("access_period", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "INVALID_ACCOUNT_START_TIME")
    expires_at = snapshot.account_started_at + timedelta(days=profile.maximum_access_days)
    if snapshot.as_of >= expires_at:
        return RuleOutcome("access_period", RuleScope.ACCOUNT, RuleStatus.ACCOUNT_FAILED,
                           "ACCOUNT_ACCESS_PERIOD_EXPIRED", (), expires_at)
    return _out("access_period", RuleScope.ACCOUNT, RuleStatus.PASS,
                "ACCOUNT_ACCESS_PERIOD_PASS")


def _inactivity_outcome(profile: PropFirmProfile, snapshot: AccountSnapshot) -> RuleOutcome:
    policy = profile.inactivity
    if policy is None:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.NOT_APPLICABLE,
                    "INACTIVITY_NOT_APPLICABLE")
    if snapshot.account_started_at is None:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_ACCOUNT_START_TIME")
    if snapshot.as_of is None:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_SNAPSHOT_TIME")
    if snapshot.account_started_at > snapshot.as_of:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "INVALID_ACCOUNT_START_TIME")
    if snapshot.as_of < snapshot.account_started_at + timedelta(days=policy.window_calendar_days):
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.PASS,
                    "INACTIVITY_WINDOW_NOT_MATURE")
    if snapshot.activity_window_days is None or snapshot.qualifying_activity_days is None:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_ACTIVITY_WINDOW_DATA")
    if snapshot.activity_window_days != policy.window_calendar_days:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "ACTIVITY_WINDOW_MISMATCH")
    if snapshot.activity_day_profit_threshold is None:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "MISSING_ACTIVITY_PROFIT_THRESHOLD")
    if snapshot.activity_day_profit_threshold != policy.minimum_day_profit:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                    "ACTIVITY_PROFIT_THRESHOLD_MISMATCH")
    if snapshot.qualifying_activity_days < policy.minimum_qualifying_days:
        return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.ACCOUNT_FAILED,
                    "INACTIVITY_REQUIREMENT_BREACHED")
    return _out("inactivity", RuleScope.ACCOUNT, RuleStatus.PASS,
                "INACTIVITY_REQUIREMENT_PASS")


def _aggregate(profile: PropFirmProfile, outcomes: list[RuleOutcome], metrics: dict,
               source_status: SourceStatus | None, payout_requested: bool = False) -> AccountEvaluationV2:
    failed = any(o.status == RuleStatus.ACCOUNT_FAILED for o in outcomes)
    account_valid = not failed and not any(
        o.scope == RuleScope.ACCOUNT and o.status == RuleStatus.INCOMPLETE_DATA for o in outcomes
    )
    trading_allowed = account_valid and not any(
        o.scope == RuleScope.TRADING and o.status in (
            RuleStatus.SESSION_BLOCKED, RuleStatus.TRADING_BLOCKED, RuleStatus.INCOMPLETE_DATA
        ) for o in outcomes
    )
    stage_met = account_valid and not any(
        o.scope == RuleScope.STAGE and o.status in (
            RuleStatus.OBJECTIVE_PENDING, RuleStatus.INCOMPLETE_DATA
        ) for o in outcomes
    )
    payout_ok = payout_requested and account_valid and stage_met and not any(
        o.status == RuleStatus.INCOMPLETE_DATA for o in outcomes
    ) and not any(
        o.scope == RuleScope.PAYOUT and o.status in (
            RuleStatus.OBJECTIVE_PENDING, RuleStatus.INCOMPLETE_DATA,
            RuleStatus.SESSION_BLOCKED, RuleStatus.ACCOUNT_FAILED
        ) for o in outcomes
    )
    if payout_requested and profile.payout.require_session_clear:
        payout_ok = payout_ok and trading_allowed
    blocked = tuple(dict.fromkeys(o.reason for o in outcomes if o.status in (
        RuleStatus.SESSION_BLOCKED, RuleStatus.TRADING_BLOCKED, RuleStatus.ACCOUNT_FAILED,
        RuleStatus.OBJECTIVE_PENDING, RuleStatus.INCOMPLETE_DATA
    )))
    return AccountEvaluationV2(
        account_valid, failed, trading_allowed, stage_met, payout_ok, tuple(outcomes),
        tuple(o.reason for o in outcomes if o.status == RuleStatus.WARNING),
        blocked,
        tuple(o.reason for o in outcomes if o.status == RuleStatus.ACCOUNT_FAILED),
        tuple(sorted(metrics.items())), profile.identity, profile.version, source_status,
    )


def _stage_consistency(profile: PropFirmProfile, snapshot: AccountSnapshot):
    from dataclasses import replace
    stage_policy = replace(profile.consistency, application=ConsistencyApplication.STAGE)
    stage_profile = replace(profile, consistency=stage_policy)
    return evaluate_consistency(stage_profile, snapshot)


def evaluate_account_v2(
    profile: PropFirmProfile, snapshot: AccountSnapshot, *, require_current_sources: bool = False
) -> AccountEvaluationV2:
    outcomes: list[RuleOutcome] = []
    metrics: dict = {}
    if snapshot.prior_account_failed is None:
        outcomes.append(_out("account_history", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_PRIOR_ACCOUNT_FAILURE_STATE"))
    elif snapshot.prior_account_failed:
        outcomes.append(_out("account_history", RuleScope.ACCOUNT, RuleStatus.ACCOUNT_FAILED,
                             "PRIOR_ACCOUNT_FAILURE"))
    for value, missing, mismatch in (
        (snapshot.stage, "MISSING_ACCOUNT_STAGE", "ACCOUNT_STAGE_MISMATCH"),
        (snapshot.starting_balance, "MISSING_STARTING_BALANCE", "STARTING_BALANCE_MISMATCH"),
    ):
        if value is None:
            outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA, missing))
        elif value != (profile.stage if missing == "MISSING_ACCOUNT_STAGE" else profile.starting_balance):
            outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA, mismatch))
    if snapshot.stage == AccountStage.UNKNOWN or profile.stage == AccountStage.UNKNOWN:
        outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                             "UNKNOWN_ACCOUNT_STAGE"))
    if snapshot.as_of is None:
        outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_SNAPSHOT_TIME"))
    elif snapshot.as_of < profile.effective_from or (
        profile.effective_to is not None and snapshot.as_of >= profile.effective_to
    ):
        outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                             "PROFILE_NOT_EFFECTIVE"))
    for value, reason in ((snapshot.current_balance, "MISSING_CURRENT_BALANCE"),
                          (snapshot.current_equity, "MISSING_CURRENT_EQUITY")):
        if value is None:
            outcomes.append(_out("profile", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA, reason))
    source_status = None
    if profile.source_review is not None:
        source_status = profile.source_review.status_at(snapshot.as_of) if snapshot.as_of else profile.source_review.status
        if source_status != SourceStatus.CURRENT_VERIFIED:
            must_block = require_current_sources or source_status in (
                SourceStatus.SOURCE_CONFLICT, SourceStatus.INCOMPLETE, SourceStatus.SOURCE_UNAVAILABLE
            )
            scope = RuleScope.ACCOUNT if must_block else RuleScope.TRADING
            status = RuleStatus.INCOMPLETE_DATA if must_block else RuleStatus.WARNING
            outcomes.append(_out("source_review", scope, status, source_status.value))
    elif require_current_sources:
        outcomes.append(_out("source_review", RuleScope.ACCOUNT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_SOURCE_REVIEW"))
    outcomes.append(_access_period_outcome(profile, snapshot))
    outcomes.append(_inactivity_outcome(profile, snapshot))
    drawdown = evaluate_drawdown_v2(profile, snapshot)
    outcomes.append(drawdown.outcome)
    metrics.update(effective_drawdown_floor=drawdown.effective_drawdown_floor,
                   drawdown_model_phase=drawdown.drawdown_model_phase,
                   remaining_drawdown=drawdown.remaining_drawdown)
    scaling, maximum_units, daily_loss_limit, scaling_metrics = _scaling_outcome(profile, snapshot)
    outcomes.append(scaling)
    metrics.update(scaling_metrics)
    outcomes.append(_daily_outcome(profile, snapshot, daily_loss_limit))
    contract, contract_metrics = _contract_outcome(profile, snapshot, maximum_units)
    outcomes.append(contract)
    metrics.update(contract_metrics)
    consistency = (evaluate_consistency(profile, snapshot)
                   if profile.consistency.application == ConsistencyApplication.STAGE
                   else _stage_consistency(profile, snapshot))
    if profile.consistency.application == ConsistencyApplication.PAYOUT_CYCLE:
        outcomes.append(_out("consistency", RuleScope.STAGE, RuleStatus.NOT_APPLICABLE,
                             "CONSISTENCY_STAGE_NOT_APPLICABLE"))
    elif consistency.reason:
        status = (RuleStatus.INCOMPLETE_DATA if consistency.reason.startswith("MISSING_")
                  or consistency.reason == "INVALID_BEST_DAY_PROFIT" else RuleStatus.OBJECTIVE_PENDING)
        outcomes.append(_out("consistency", RuleScope.STAGE, status, consistency.reason))
    else:
        outcomes.append(_out("consistency", RuleScope.STAGE,
                             RuleStatus.PASS if profile.consistency.enabled else RuleStatus.NOT_APPLICABLE,
                             "CONSISTENCY_PASS" if profile.consistency.enabled else "CONSISTENCY_NOT_APPLICABLE"))
    metrics["best_day_fraction"] = consistency.best_day_fraction
    if profile.trading_days.minimum_days:
        if snapshot.trading_days is None:
            outcomes.append(_out("trading_days", RuleScope.STAGE, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_TRADING_DAYS"))
        elif snapshot.trading_days < profile.trading_days.minimum_days:
            outcomes.append(_out("trading_days", RuleScope.STAGE, RuleStatus.OBJECTIVE_PENDING,
                                 "MINIMUM_TRADING_DAYS_NOT_MET"))
        else:
            outcomes.append(_out("trading_days", RuleScope.STAGE, RuleStatus.PASS, "TRADING_DAYS_PASS"))
    if profile.profit_target is not None:
        if snapshot.total_profit is None:
            outcomes.append(_out("profit_target", RuleScope.STAGE, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_TOTAL_PROFIT"))
        else:
            metrics["profit_target_remaining"] = profile.profit_target - snapshot.total_profit
            outcomes.append(_out("profit_target", RuleScope.STAGE,
                                 RuleStatus.PASS if snapshot.total_profit >= profile.profit_target
                                 else RuleStatus.OBJECTIVE_PENDING,
                                 "PROFIT_TARGET_PASS" if snapshot.total_profit >= profile.profit_target
                                 else "PROFIT_TARGET_NOT_MET"))
    return _aggregate(profile, outcomes, metrics, source_status)


def evaluate_payout_v2(
    profile: PropFirmProfile, snapshot: AccountSnapshot, request: PayoutRequest,
    *, require_current_sources: bool = False
) -> AccountEvaluationV2:
    """Evaluate a request from supplied state; never performs or records a payout."""
    account = evaluate_account_v2(profile, snapshot, require_current_sources=require_current_sources)
    outcomes = list(account.outcomes)
    metrics = dict(account.metrics)
    policy = profile.payout
    metrics["requested_payout"] = request.amount
    if not policy.enabled:
        outcomes.append(_out("payout", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                             "PAYOUT_DISABLED"))
        return _aggregate(profile, outcomes, metrics, account.source_status, True)

    cycle_required = any((
        policy.minimum_winning_days_per_cycle, policy.minimum_trading_days_per_cycle,
        policy.minimum_qualifying_days_per_cycle,
        policy.minimum_profit_since_last_payout is not None, policy.consistency_per_cycle,
        bool(policy.tiers), policy.maximum_payout_count is not None,
    ))
    cycle = snapshot.payout_cycle
    if cycle_required and cycle is None:
        outcomes.append(_out("payout_cycle", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_PAYOUT_CYCLE"))
    if cycle is not None:
        if not cycle.cycle_id or cycle.current_cycle_start is None:
            outcomes.append(_out("payout_cycle", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "INCOMPLETE_PAYOUT_CYCLE_IDENTITY"))
        elif snapshot.as_of is not None and cycle.current_cycle_start > snapshot.as_of:
            outcomes.append(_out("payout_cycle", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "INVALID_PAYOUT_CYCLE_START"))
        if cycle.requested_payout_amount is not None and cycle.requested_payout_amount != request.amount:
            outcomes.append(_out("payout_cycle", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "PAYOUT_REQUEST_MISMATCH"))
        if (snapshot.withdrawals is not None and cycle.withdrawals_total is not None
                and snapshot.withdrawals != cycle.withdrawals_total):
            outcomes.append(_out("payout_cycle", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "WITHDRAWALS_MISMATCH"))

    if policy.minimum_payout_amount is not None and request.amount < policy.minimum_payout_amount:
        outcomes.append(_out("payout_minimum", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                             "PAYOUT_MINIMUM_AMOUNT_NOT_MET"))
    if policy.minimum_trading_days:
        if snapshot.trading_days is None:
            outcomes.append(_out("payout_days", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_TRADING_DAYS"))
        elif snapshot.trading_days < policy.minimum_trading_days:
            outcomes.append(_out("payout_days", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_MINIMUM_TRADING_DAYS_NOT_MET"))

    if cycle is not None:
        if policy.maximum_payout_count is not None:
            if cycle.payout_count is None:
                outcomes.append(_out("payout_count", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_PAYOUT_COUNT"))
            elif cycle.payout_count >= policy.maximum_payout_count:
                outcomes.append(_out("payout_count", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_COUNT_LIMIT_REACHED"))
        if policy.minimum_trading_days_per_cycle:
            if cycle.trading_days_since_last_payout is None:
                outcomes.append(_out("payout_cycle_days", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_TRADING_DAYS"))
            elif cycle.trading_days_since_last_payout < policy.minimum_trading_days_per_cycle:
                outcomes.append(_out("payout_cycle_days", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_CYCLE_TRADING_DAYS_NOT_MET"))
        if policy.minimum_winning_days_per_cycle:
            if cycle.winning_days_since_last_payout is None:
                outcomes.append(_out("payout_cycle_wins", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_WINNING_DAYS"))
            elif cycle.winning_days_since_last_payout < policy.minimum_winning_days_per_cycle:
                outcomes.append(_out("payout_cycle_wins", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_CYCLE_WINNING_DAYS_NOT_MET"))
        if policy.minimum_qualifying_days_per_cycle:
            if cycle.qualifying_days_since_last_payout is None:
                outcomes.append(_out("payout_cycle_qualifying_days", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA, "MISSING_CYCLE_QUALIFYING_DAYS"))
            elif cycle.qualifying_day_profit_threshold is None:
                outcomes.append(_out("payout_cycle_qualifying_days", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_QUALIFYING_DAY_THRESHOLD"))
            elif cycle.qualifying_day_profit_threshold != policy.minimum_qualifying_day_profit:
                outcomes.append(_out("payout_cycle_qualifying_days", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA,
                                     "CYCLE_QUALIFYING_DAY_THRESHOLD_MISMATCH"))
            elif cycle.qualifying_days_since_last_payout < policy.minimum_qualifying_days_per_cycle:
                outcomes.append(_out("payout_cycle_qualifying_days", RuleScope.PAYOUT,
                                     RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_CYCLE_QUALIFYING_DAYS_NOT_MET"))
        if policy.minimum_profit_since_last_payout is not None:
            if cycle.profit_since_last_payout is None:
                outcomes.append(_out("payout_cycle_profit", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_PROFIT"))
            elif cycle.profit_since_last_payout < policy.minimum_profit_since_last_payout:
                outcomes.append(_out("payout_cycle_profit", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_CYCLE_PROFIT_NOT_MET"))
        if policy.consistency_per_cycle:
            if not profile.consistency.enabled or profile.consistency.application == ConsistencyApplication.STAGE:
                outcomes.append(_out("payout_cycle_consistency", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA, "UNSUPPORTED_POLICY"))
            elif cycle.profit_since_last_payout is None or cycle.best_day_profit_since_last_payout is None:
                outcomes.append(_out("payout_cycle_consistency", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA, "MISSING_CYCLE_CONSISTENCY_DATA"))
            elif cycle.best_day_profit_since_last_payout < 0:
                outcomes.append(_out("payout_cycle_consistency", RuleScope.PAYOUT,
                                     RuleStatus.INCOMPLETE_DATA, "INVALID_CYCLE_BEST_DAY_PROFIT"))
            elif cycle.profit_since_last_payout <= 0 or (
                cycle.profit_since_last_payout < profile.consistency.minimum_profit_basis
            ):
                outcomes.append(_out("payout_cycle_consistency", RuleScope.PAYOUT,
                                     RuleStatus.OBJECTIVE_PENDING, "INSUFFICIENT_CYCLE_PROFIT_BASIS"))
            else:
                fraction = cycle.best_day_profit_since_last_payout / cycle.profit_since_last_payout
                metrics["cycle_best_day_fraction"] = fraction
                breached = (
                    fraction > profile.consistency.maximum_best_day_fraction
                    if profile.consistency.maximum_is_inclusive
                    else fraction >= profile.consistency.maximum_best_day_fraction
                )
                if breached:
                    outcomes.append(_out("payout_cycle_consistency", RuleScope.PAYOUT,
                                         RuleStatus.OBJECTIVE_PENDING,
                                         "PAYOUT_CYCLE_CONSISTENCY_NOT_MET"))

    tier = None
    if policy.tiers:
        if cycle is None or cycle.payout_count is None:
            outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_PAYOUT_COUNT"))
        else:
            tier = next((t for t in reversed(policy.tiers)
                         if t.from_payout_count <= cycle.payout_count), None)
            if tier is None:
                outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "UNSUPPORTED_POLICY"))
    if tier is not None:
        if tier.minimum_winning_days_per_cycle is not None:
            if cycle.winning_days_since_last_payout is None:
                outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_WINNING_DAYS"))
            elif cycle.winning_days_since_last_payout < tier.minimum_winning_days_per_cycle:
                outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_TIER_WINNING_DAYS_NOT_MET"))
        if tier.minimum_profit_since_last_payout is not None:
            if cycle.profit_since_last_payout is None:
                outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_CYCLE_PROFIT"))
            elif cycle.profit_since_last_payout < tier.minimum_profit_since_last_payout:
                outcomes.append(_out("payout_tier", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_TIER_PROFIT_NOT_MET"))
        metrics["payout_tier_start_count"] = tier.from_payout_count

    withdrawals = snapshot.withdrawals
    if cycle is not None:
        if cycle.withdrawals_total is None:
            outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_CYCLE_WITHDRAWALS"))
        else:
            withdrawals = cycle.withdrawals_total
    if withdrawals is None:
        outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_WITHDRAWALS"))
    elif withdrawals < 0:
        outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "INVALID_WITHDRAWALS"))
    if snapshot.total_profit is None:
        outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_TOTAL_PROFIT"))
        available = None
    elif withdrawals is None:
        available = None
    else:
        available = snapshot.total_profit - withdrawals
        metrics["available_profit"] = available
        if available <= 0 or request.amount > available:
            outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_EXCEEDS_AVAILABLE_PROFIT"))
        if policy.minimum_profit is not None and available < policy.minimum_profit:
            outcomes.append(_out("payout_profit", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_MINIMUM_PROFIT_NOT_MET"))

    for cap in (policy.maximum_payout_amount, tier.maximum_amount if tier else None):
        if cap is not None and request.amount > cap:
            outcomes.append(_out("payout_amount", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_AMOUNT_LIMIT_BREACHED", cap=cap))
    if policy.maximum_fraction_basis == PayoutFractionBasis.CURRENT_BALANCE:
        fraction_base = snapshot.current_balance
        missing_base = "MISSING_CURRENT_BALANCE"
    else:
        fraction_base = available
        missing_base = "MISSING_AVAILABLE_PROFIT"
    for cap in (policy.maximum_payout_fraction, tier.maximum_fraction if tier else None):
        if cap is None:
            continue
        if fraction_base is None:
            outcomes.append(_out("payout_fraction", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 missing_base))
        elif request.amount > fraction_base * cap:
            outcomes.append(_out("payout_fraction", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_FRACTION_LIMIT_BREACHED", fraction=cap))

    if snapshot.current_balance is None:
        outcomes.append(_out("payout_balance", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "MISSING_CURRENT_BALANCE"))
    else:
        after = snapshot.current_balance - request.amount
        metrics["post_payout_balance"] = after
        if policy.minimum_balance is not None and after < policy.minimum_balance:
            outcomes.append(_out("payout_balance", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                 "PAYOUT_MINIMUM_BALANCE_NOT_MET"))
        if policy.minimum_buffer is not None:
            floor = dict(account.metrics)["effective_drawdown_floor"]
            observed = _observed(snapshot, _breach_basis(profile))
            if floor is None or observed is None:
                outcomes.append(_out("payout_buffer", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_DRAWDOWN_FLOOR_OR_BASIS"))
            else:
                buffer = observed - request.amount - floor
                metrics["post_payout_buffer"] = buffer
                if buffer < policy.minimum_buffer:
                    outcomes.append(_out("payout_buffer", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                         "PAYOUT_MINIMUM_BUFFER_NOT_MET"))
    if policy.consistency_required and (not profile.consistency.enabled or profile.consistency.application == ConsistencyApplication.PAYOUT_CYCLE):
        outcomes.append(_out("payout_consistency", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                             "PAYOUT_CONSISTENCY_POLICY_MISSING"))
    elif policy.consistency_required:
        consistency = _stage_consistency(profile, snapshot)
        if consistency.reason:
            outcomes.append(_out("payout_consistency", RuleScope.PAYOUT,
                                 RuleStatus.INCOMPLETE_DATA if consistency.reason.startswith("MISSING_")
                                 else RuleStatus.OBJECTIVE_PENDING, consistency.reason))
    if policy.minimum_days_since_prior_payout:
        count = cycle.payout_count if cycle is not None else snapshot.prior_payout_count
        last = cycle.last_payout_at if cycle is not None else snapshot.last_payout_at
        if count is None:
            outcomes.append(_out("payout_wait", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                 "MISSING_PAYOUT_COUNT"))
        elif count > 0:
            if last is None or snapshot.as_of is None:
                outcomes.append(_out("payout_wait", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "MISSING_LAST_PAYOUT_TIME"))
            elif last > snapshot.as_of:
                outcomes.append(_out("payout_wait", RuleScope.PAYOUT, RuleStatus.INCOMPLETE_DATA,
                                     "INVALID_LAST_PAYOUT_TIME"))
            elif snapshot.as_of - last < timedelta(days=policy.minimum_days_since_prior_payout):
                outcomes.append(_out("payout_wait", RuleScope.PAYOUT, RuleStatus.OBJECTIVE_PENDING,
                                     "PAYOUT_COOLDOWN_NOT_MET"))
    return _aggregate(profile, outcomes, metrics, account.source_status, True)
