"""Immutable, firm-neutral configuration and account snapshots for rule evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json


class AccountStage(str, Enum):
    EVALUATION = "EVALUATION"
    FUNDED = "FUNDED"
    EXPRESS = "EXPRESS"
    PRO = "PRO"
    LIVE = "LIVE"
    UNKNOWN = "UNKNOWN"


class DrawdownModel(str, Enum):
    STATIC = "STATIC"
    TRAILING_INTRADAY = "TRAILING_INTRADAY"
    TRAILING_END_OF_DAY = "TRAILING_END_OF_DAY"
    BALANCE_BASED = "BALANCE_BASED"
    EQUITY_BASED = "EQUITY_BASED"
    NONE = "NONE"


class ValueBasis(str, Enum):
    BALANCE = "BALANCE"
    EQUITY = "EQUITY"
    MIN_BALANCE_OR_EQUITY = "MIN_BALANCE_OR_EQUITY"


class ConsistencyMode(str, Enum):
    TOTAL_PROFIT = "TOTAL_PROFIT"
    REALIZED_PNL = "REALIZED_PNL"


def _money(value: Decimal | None, name: str, *, positive: bool = False) -> None:
    if value is None:
        if positive:
            raise ValueError(f"{name} is required")
        return
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")


def _nonnegative(value: int | None, name: str) -> None:
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f"{name} must be a nonnegative integer")


def _bool(value: bool, name: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")


def _aware(value: datetime | None, name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")



class DailyLossEnforcement(str, Enum):
    SESSION_BLOCK = "SESSION_BLOCK"
    ACCOUNT_FAIL = "ACCOUNT_FAIL"
    WARNING_ONLY = "WARNING_ONLY"
    OBJECTIVE_ONLY = "OBJECTIVE_ONLY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ContractLimitEnforcement(str, Enum):
    ACCOUNT_FAIL = "ACCOUNT_FAIL"
    TRADING_BLOCK = "TRADING_BLOCK"
    WARNING_ONLY = "WARNING_ONLY"
    OBJECTIVE_ONLY = "OBJECTIVE_ONLY"


class ResetBoundary(str, Enum):
    SESSION_END = "SESSION_END"
    TRADING_DAY_END = "TRADING_DAY_END"


class ReferenceUpdateMode(str, Enum):
    FIXED_START = "FIXED_START"
    INTRADAY_EQUITY = "INTRADAY_EQUITY"
    END_OF_DAY_BALANCE = "END_OF_DAY_BALANCE"


class ConsistencyApplication(str, Enum):
    STAGE = "STAGE"
    PAYOUT_CYCLE = "PAYOUT_CYCLE"
    BOTH = "BOTH"


class PayoutFractionBasis(str, Enum):
    AVAILABLE_PROFIT = "AVAILABLE_PROFIT"
    CURRENT_BALANCE = "CURRENT_BALANCE"


class SourceStatus(str, Enum):
    CURRENT_VERIFIED = "CURRENT_VERIFIED"
    STALE_REVIEW_REQUIRED = "STALE_REVIEW_REQUIRED"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    INCOMPLETE = "INCOMPLETE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


@dataclass(frozen=True)
class SourceEvidence:
    source_url: str
    source_title: str
    retrieved_at_utc: datetime
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    rule_heading: str | None = None
    normalized_source_hash: str | None = None
    temporary: bool = False
    review_required: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.source_url, str) or not self.source_url.startswith(("https://", "http://"))
                or not isinstance(self.source_title, str) or not self.source_title.strip()):
            raise ValueError("source URL and title are required")
        _aware(self.retrieved_at_utc, "retrieved_at_utc")
        if self.retrieved_at_utc is None or self.retrieved_at_utc.utcoffset().total_seconds() != 0:
            raise ValueError("retrieved_at_utc must be UTC")
        _aware(self.effective_from, "source effective_from")
        _aware(self.effective_to, "source effective_to")
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("source effective_to must follow effective_from")
        _bool(self.temporary, "temporary")
        _bool(self.review_required, "review_required")


@dataclass(frozen=True)
class SourceReview:
    status: SourceStatus
    reviewed_at: datetime
    sources: tuple[SourceEvidence, ...] = ()
    review_due_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, SourceStatus):
            raise ValueError("invalid source status")
        _aware(self.reviewed_at, "reviewed_at")
        _aware(self.review_due_at, "review_due_at")
        if self.reviewed_at is None or not isinstance(self.sources, tuple):
            raise ValueError("review date and immutable source tuple required")
        if any(not isinstance(source, SourceEvidence) for source in self.sources):
            raise ValueError("invalid source evidence")
        if self.status == SourceStatus.CURRENT_VERIFIED and not self.sources:
            raise ValueError("verified review requires source evidence")
        if self.review_due_at is not None and self.review_due_at < self.reviewed_at:
            raise ValueError("review_due_at cannot precede reviewed_at")
        if any(source.retrieved_at_utc > self.reviewed_at for source in self.sources):
            raise ValueError("source cannot be retrieved after review")

    def status_at(self, at: datetime) -> SourceStatus:
        _aware(at, "at")
        if at is None:
            raise ValueError("at is required")
        if (self.status == SourceStatus.CURRENT_VERIFIED and self.review_due_at is not None
                and at > self.review_due_at):
            return SourceStatus.STALE_REVIEW_REQUIRED
        return self.status


@dataclass(frozen=True)
class DrawdownTransition:
    floor_lock: bool = False
    post_event_payout_count: int | None = None
    post_event_fixed_floor: Decimal | None = None

    def __post_init__(self) -> None:
        _bool(self.floor_lock, "floor_lock")
        _nonnegative(self.post_event_payout_count, "post_event_payout_count")
        _money(self.post_event_fixed_floor, "post_event_fixed_floor")
        if (self.post_event_payout_count is None) != (self.post_event_fixed_floor is None):
            raise ValueError("post-event count and fixed floor must be configured together")
        if self.post_event_payout_count == 0:
            raise ValueError("post-event count must be positive")


@dataclass(frozen=True)
class ExposureWeight:
    key: str
    units_per_contract: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("weight key is required")
        _money(self.units_per_contract, "units_per_contract", positive=True)


@dataclass(frozen=True)
class InstrumentGroup:
    instrument: str
    product_group: str

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise ValueError("instrument is required")
        if not isinstance(self.product_group, str) or not self.product_group.strip():
            raise ValueError("product_group is required")


@dataclass(frozen=True)
class WeightedExposurePolicy:
    maximum_units: Decimal
    instrument_weights: tuple[ExposureWeight, ...] = ()
    product_group_weights: tuple[ExposureWeight, ...] = ()
    instrument_groups: tuple[InstrumentGroup, ...] = ()

    def __post_init__(self) -> None:
        _money(self.maximum_units, "maximum_units", positive=True)
        for mapping in (self.instrument_weights, self.product_group_weights):
            if not isinstance(mapping, tuple) or any(not isinstance(v, ExposureWeight) for v in mapping):
                raise ValueError("exposure weights must be immutable tuples")
            keys = [v.key for v in mapping]
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate exposure weight")
        if not isinstance(self.instrument_groups, tuple) or any(not isinstance(v, InstrumentGroup) for v in self.instrument_groups):
            raise ValueError("instrument_groups must be an immutable tuple")
        names = [v.instrument for v in self.instrument_groups]
        if len(names) != len(set(names)):
            raise ValueError("duplicate instrument group mapping")
        if self.product_group_weights and not self.instrument_groups:
            raise ValueError("group weights require trusted instrument mappings")
        if not self.instrument_weights and not self.product_group_weights:
            raise ValueError("weighted exposure requires at least one weight")


@dataclass(frozen=True)
class ExposurePosition:
    instrument: str
    quantity: int
    product_group: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, str) or not self.instrument.strip():
            raise ValueError("instrument is required")
        _nonnegative(self.quantity, "quantity")
        if self.product_group is not None and not isinstance(self.product_group, str):
            raise ValueError("product_group must be a string")


@dataclass(frozen=True)
class PayoutTier:
    from_payout_count: int
    maximum_amount: Decimal | None = None
    maximum_fraction: Decimal | None = None
    minimum_profit_since_last_payout: Decimal | None = None
    minimum_winning_days_per_cycle: int | None = None

    def __post_init__(self) -> None:
        _nonnegative(self.from_payout_count, "from_payout_count")
        if self.maximum_amount is not None:
            _money(self.maximum_amount, "tier maximum_amount", positive=True)
        if self.maximum_fraction is not None:
            _money(self.maximum_fraction, "tier maximum_fraction", positive=True)
            if self.maximum_fraction > 1:
                raise ValueError("tier maximum_fraction cannot exceed one")
        if self.minimum_profit_since_last_payout is not None:
            _money(self.minimum_profit_since_last_payout, "tier minimum profit", positive=True)
        _nonnegative(self.minimum_winning_days_per_cycle, "tier minimum winning days")
        if all(v is None for v in (self.maximum_amount, self.maximum_fraction,
                                    self.minimum_profit_since_last_payout,
                                    self.minimum_winning_days_per_cycle)):
            raise ValueError("tier must configure at least one rule")


@dataclass(frozen=True)
class PayoutCycleSnapshot:
    cycle_id: str | None = None
    payout_count: int | None = None
    last_payout_at: datetime | None = None
    profit_since_last_payout: Decimal | None = None
    winning_days_since_last_payout: int | None = None
    trading_days_since_last_payout: int | None = None
    current_cycle_start: datetime | None = None
    withdrawals_total: Decimal | None = None
    requested_payout_amount: Decimal | None = None
    best_day_profit_since_last_payout: Decimal | None = None

    def __post_init__(self) -> None:
        if self.cycle_id is not None and (not isinstance(self.cycle_id, str) or not self.cycle_id.strip()):
            raise ValueError("cycle_id must be a nonempty string")
        for name in ("payout_count", "winning_days_since_last_payout", "trading_days_since_last_payout"):
            _nonnegative(getattr(self, name), name)
        for name in ("profit_since_last_payout", "withdrawals_total",
                     "requested_payout_amount", "best_day_profit_since_last_payout"):
            _money(getattr(self, name), name)
        _aware(self.last_payout_at, "last_payout_at")
        _aware(self.current_cycle_start, "current_cycle_start")


@dataclass(frozen=True)
class DrawdownPolicy:
    model: DrawdownModel
    maximum_loss: Decimal | None = None
    breach_basis: ValueBasis | None = None
    floor_cap: Decimal | None = None
    transition: DrawdownTransition | None = None
    reference_update_mode: ReferenceUpdateMode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, DrawdownModel):
            raise ValueError("drawdown model must be a DrawdownModel")
        if self.breach_basis is not None and not isinstance(self.breach_basis, ValueBasis):
            raise ValueError("breach_basis must be a ValueBasis")
        if self.transition is not None and not isinstance(self.transition, DrawdownTransition):
            raise ValueError("invalid drawdown transition")
        if self.reference_update_mode is not None and not isinstance(self.reference_update_mode, ReferenceUpdateMode):
            raise ValueError("invalid reference update mode")
        if self.model == DrawdownModel.NONE:
            if any(v is not None for v in (self.maximum_loss, self.breach_basis, self.floor_cap, self.transition, self.reference_update_mode)):
                raise ValueError("NONE drawdown cannot carry limits")
            return
        _money(self.maximum_loss, "maximum_loss", positive=True)
        if self.maximum_loss is None:
            raise ValueError("maximum_loss is required")
        if self.model == DrawdownModel.BALANCE_BASED:
            expected = ValueBasis.BALANCE
        elif self.model == DrawdownModel.EQUITY_BASED:
            expected = ValueBasis.EQUITY
        else:
            expected = None
        if expected is not None and self.breach_basis not in (None, expected):
            raise ValueError("breach_basis conflicts with drawdown model")
        if expected is None and self.breach_basis is None:
            raise ValueError("breach_basis is required")
        _money(self.floor_cap, "floor_cap")


@dataclass(frozen=True)
class DailyLossPolicy:
    limit: Decimal | None = None
    enforcement: DailyLossEnforcement = DailyLossEnforcement.ACCOUNT_FAIL
    reset_boundary: ResetBoundary = ResetBoundary.SESSION_END

    def __post_init__(self) -> None:
        if not isinstance(self.enforcement, DailyLossEnforcement):
            raise ValueError("invalid daily loss enforcement")
        if not isinstance(self.reset_boundary, ResetBoundary):
            raise ValueError("invalid reset boundary")
        _money(self.limit, "daily loss limit", positive=self.limit is not None)
        if self.limit is None and self.enforcement not in (DailyLossEnforcement.ACCOUNT_FAIL, DailyLossEnforcement.NOT_APPLICABLE):
            raise ValueError("active daily loss enforcement requires a limit")
        if self.limit is not None and self.enforcement == DailyLossEnforcement.NOT_APPLICABLE:
            raise ValueError("NOT_APPLICABLE cannot carry a limit")


@dataclass(frozen=True)
class ContractLimitPolicy:
    maximum_open: int | None
    maximum_traded: int | None = None
    weighted_exposure: WeightedExposurePolicy | None = None
    breach_enforcement: ContractLimitEnforcement = ContractLimitEnforcement.ACCOUNT_FAIL
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        _nonnegative(self.maximum_open, "maximum_open")
        _nonnegative(self.maximum_traded, "maximum_traded")
        if not isinstance(self.breach_enforcement, ContractLimitEnforcement):
            raise ValueError("invalid contract limit enforcement")
        if self.weighted_exposure is not None and not isinstance(self.weighted_exposure, WeightedExposurePolicy):
            raise ValueError("invalid weighted_exposure policy")
        if self.unavailable_reason is not None and (
            not isinstance(self.unavailable_reason, str) or not self.unavailable_reason.strip()
        ):
            raise ValueError("unavailable_reason must be a nonempty string")
        if self.maximum_open == 0:
            raise ValueError("maximum_open must be positive")
        if self.maximum_traded == 0:
            raise ValueError("maximum_traded must be positive")
        if self.maximum_open is None and self.weighted_exposure is None and self.unavailable_reason is None:
            raise ValueError("maximum_open, weighted_exposure, or unavailable_reason is required")
        if self.unavailable_reason is not None and any((
            self.maximum_open is not None, self.maximum_traded is not None,
            self.weighted_exposure is not None,
        )):
            raise ValueError("unavailable contract policy cannot carry numeric limits")


@dataclass(frozen=True)
class TradingDayPolicy:
    minimum_days: int = 0

    def __post_init__(self) -> None:
        _nonnegative(self.minimum_days, "minimum_days")


@dataclass(frozen=True)
class ConsistencyPolicy:
    enabled: bool
    maximum_best_day_fraction: Decimal | None = None
    minimum_profit_basis: Decimal | None = None
    calculation_mode: ConsistencyMode | None = None
    application: ConsistencyApplication = ConsistencyApplication.STAGE

    def __post_init__(self) -> None:
        _bool(self.enabled, "consistency enabled")
        if self.calculation_mode is not None and not isinstance(self.calculation_mode, ConsistencyMode):
            raise ValueError("calculation_mode must be a ConsistencyMode")
        if not isinstance(self.application, ConsistencyApplication):
            raise ValueError("invalid consistency application")
        if not self.enabled and self.application != ConsistencyApplication.STAGE:
            raise ValueError("disabled consistency cannot have payout-cycle application")
        if not self.enabled:
            if any(v is not None for v in (
                self.maximum_best_day_fraction, self.minimum_profit_basis, self.calculation_mode
            )):
                raise ValueError("disabled consistency policy cannot carry limits")
            return
        _money(self.maximum_best_day_fraction, "maximum_best_day_fraction", positive=True)
        _money(self.minimum_profit_basis, "minimum_profit_basis", positive=True)
        if (self.maximum_best_day_fraction is None
                or self.maximum_best_day_fraction > 1
                or self.minimum_profit_basis is None
                or self.calculation_mode is None):
            raise ValueError("enabled consistency policy requires fraction, basis and mode")


@dataclass(frozen=True)
class PayoutPolicy:
    enabled: bool
    minimum_trading_days: int = 0
    minimum_buffer: Decimal | None = None
    minimum_balance: Decimal | None = None
    minimum_profit: Decimal | None = None
    maximum_payout_amount: Decimal | None = None
    maximum_payout_fraction: Decimal | None = None
    consistency_required: bool = False
    minimum_days_since_prior_payout: int = 0
    minimum_winning_days_per_cycle: int = 0
    minimum_trading_days_per_cycle: int = 0
    minimum_profit_since_last_payout: Decimal | None = None
    minimum_payout_amount: Decimal | None = None
    maximum_fraction_basis: PayoutFractionBasis = PayoutFractionBasis.AVAILABLE_PROFIT
    tiers: tuple[PayoutTier, ...] = ()
    consistency_per_cycle: bool = False
    require_session_clear: bool = True

    def __post_init__(self) -> None:
        for name in ("enabled", "consistency_required", "consistency_per_cycle", "require_session_clear"):
            _bool(getattr(self, name), name)
        _nonnegative(self.minimum_trading_days, "minimum_trading_days")
        _nonnegative(self.minimum_days_since_prior_payout, "minimum_days_since_prior_payout")
        _nonnegative(self.minimum_winning_days_per_cycle, "minimum_winning_days_per_cycle")
        _nonnegative(self.minimum_trading_days_per_cycle, "minimum_trading_days_per_cycle")
        if not isinstance(self.maximum_fraction_basis, PayoutFractionBasis):
            raise ValueError("invalid maximum_fraction_basis")
        if not isinstance(self.tiers, tuple) or any(not isinstance(t, PayoutTier) for t in self.tiers):
            raise ValueError("tiers must be an immutable tuple")
        counts = [t.from_payout_count for t in self.tiers]
        if len(counts) != len(set(counts)) or counts != sorted(counts):
            raise ValueError("payout tiers must be unique and sorted")
        for name in ("minimum_profit_since_last_payout", "minimum_payout_amount"):
            value = getattr(self, name)
            if value is not None:
                _money(value, name, positive=True)
        for name in ("minimum_buffer", "minimum_balance", "minimum_profit", "maximum_payout_amount"):
            _money(getattr(self, name), name)
        if any(getattr(self, name) is not None and getattr(self, name) < 0 for name in (
            "minimum_buffer", "minimum_balance", "minimum_profit"
        )):
            raise ValueError("payout minimums cannot be negative")
        _money(self.maximum_payout_fraction, "maximum_payout_fraction")
        if self.maximum_payout_fraction is not None and not (0 < self.maximum_payout_fraction <= 1):
            raise ValueError("maximum_payout_fraction must be in (0, 1]")
        if self.maximum_payout_amount is not None and self.maximum_payout_amount <= 0:
            raise ValueError("maximum_payout_amount must be positive")
        if not self.enabled and any((
            self.minimum_trading_days, self.minimum_buffer is not None,
            self.minimum_balance is not None, self.minimum_profit is not None,
            self.maximum_payout_amount is not None, self.maximum_payout_fraction is not None,
            self.consistency_required, self.minimum_days_since_prior_payout,
            self.minimum_winning_days_per_cycle, self.minimum_trading_days_per_cycle,
            self.minimum_profit_since_last_payout is not None, self.minimum_payout_amount is not None,
            self.maximum_fraction_basis != PayoutFractionBasis.AVAILABLE_PROFIT,
            bool(self.tiers), self.consistency_per_cycle, not self.require_session_clear
        )):
            raise ValueError("disabled payout policy cannot carry requirements")


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: _canonical(getattr(value, f.name)) for f in fields(value) if f.name != "config_hash"}
    if isinstance(value, tuple):
        return [_canonical(v) for v in value]
    return value


@dataclass(frozen=True)
class PropFirmProfile:
    firm_id: str
    program_id: str
    stage: AccountStage
    version: str
    effective_from: datetime
    account_size: Decimal
    starting_balance: Decimal
    drawdown: DrawdownPolicy
    daily_loss: DailyLossPolicy
    contract_limit: ContractLimitPolicy
    consistency: ConsistencyPolicy
    payout: PayoutPolicy
    trading_days: TradingDayPolicy = field(default_factory=TradingDayPolicy)
    profit_target: Decimal | None = None
    effective_to: datetime | None = None
    source_reference: str | None = None
    allow_zero_starting_balance: bool = False
    source_review: SourceReview | None = None
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
        _bool(self.allow_zero_starting_balance, "allow_zero_starting_balance")
        if not all(isinstance(v, str) and v.strip() for v in (
            self.firm_id, self.program_id, self.version
        )):
            raise ValueError("profile identity fields must be nonempty strings")
        if self.source_reference is not None and not isinstance(self.source_reference, str):
            raise ValueError("source_reference must be a string")
        if not isinstance(self.stage, AccountStage):
            raise ValueError("stage must be an AccountStage")
        if not isinstance(self.drawdown, DrawdownPolicy) or not isinstance(self.daily_loss, DailyLossPolicy):
            raise ValueError("drawdown and daily_loss policies are required")
        if not isinstance(self.contract_limit, ContractLimitPolicy) or not isinstance(self.consistency, ConsistencyPolicy):
            raise ValueError("contract_limit and consistency policies are required")
        if not isinstance(self.payout, PayoutPolicy) or not isinstance(self.trading_days, TradingDayPolicy):
            raise ValueError("payout and trading_days policies are required")
        if self.effective_from is None:
            raise ValueError("effective_from is required")
        _aware(self.effective_from, "effective_from")
        _aware(self.effective_to, "effective_to")
        if self.effective_to is not None and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must follow effective_from")
        _money(self.account_size, "account_size", positive=True)
        _money(self.starting_balance, "starting_balance", positive=True if not self.allow_zero_starting_balance else False)
        if self.starting_balance is None or self.starting_balance < 0:
            raise ValueError("starting_balance must be nonnegative")
        if self.source_review is not None and not isinstance(self.source_review, SourceReview):
            raise ValueError("invalid source_review")
        if self.profit_target is not None:
            _money(self.profit_target, "profit_target", positive=True)
        payload = json.dumps(_canonical(self), sort_keys=True, separators=(",", ":"))
        object.__setattr__(self, "config_hash", hashlib.sha256(payload.encode("utf-8")).hexdigest())

    @property
    def identity(self) -> str:
        return f"{self.firm_id}/{self.program_id}/{self.stage.value}/{self.version}/{self.config_hash}"


@dataclass(frozen=True)
class AccountProgram:
    firm_id: str
    program_id: str
    profiles: tuple[PropFirmProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profiles, tuple) or not self.profiles:
            raise ValueError("program needs a nonempty tuple of profiles")
        keys = set()
        for profile in self.profiles:
            if not isinstance(profile, PropFirmProfile):
                raise ValueError("program profiles must be PropFirmProfile values")
            if (profile.firm_id, profile.program_id) != (self.firm_id, self.program_id):
                raise ValueError("profile does not belong to program")
            key = (profile.account_size, profile.stage, profile.version)
            if key in keys:
                raise ValueError("duplicate stage/size/version profile")
            keys.add(key)

    def select(self, account_size: Decimal, stage: AccountStage, at: datetime) -> PropFirmProfile:
        _money(account_size, "account_size", positive=True)
        if not isinstance(stage, AccountStage):
            raise ValueError("stage must be an AccountStage")
        if at is None:
            raise ValueError("at is required")
        _aware(at, "at")
        matches = tuple(p for p in self.profiles if p.account_size == account_size
                        and p.stage == stage and p.effective_from <= at
                        and (p.effective_to is None or at < p.effective_to))
        if len(matches) != 1:
            raise ValueError("profile selection must resolve to exactly one active profile")
        return matches[0]


@dataclass(frozen=True)
class AccountSnapshot:
    as_of: datetime | None = None
    stage: AccountStage | None = None
    starting_balance: Decimal | None = None
    current_balance: Decimal | None = None
    current_equity: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    daily_pnl: Decimal | None = None
    highest_balance: Decimal | None = None
    highest_equity: Decimal | None = None
    highest_end_of_day_balance: Decimal | None = None
    contracts_open: int | None = None
    contracts_traded: int | None = None
    trading_days: int | None = None
    best_day_profit: Decimal | None = None
    total_profit: Decimal | None = None
    withdrawals: Decimal | None = None
    prior_payout_count: int | None = None
    last_payout_at: datetime | None = None
    session_id: str | None = None
    daily_pnl_session_id: str | None = None
    prior_session_blocked: bool | None = None
    blocked_session_id: str | None = None
    session_ends_at: datetime | None = None
    trading_day_ends_at: datetime | None = None
    prior_drawdown_floor: Decimal | None = None
    prior_account_failed: bool | None = None
    exposures: tuple[ExposurePosition, ...] | None = None
    payout_cycle: PayoutCycleSnapshot | None = None

    def __post_init__(self) -> None:
        _aware(self.as_of, "as_of")
        _aware(self.last_payout_at, "last_payout_at")
        _aware(self.session_ends_at, "session_ends_at")
        _aware(self.trading_day_ends_at, "trading_day_ends_at")
        _money(self.prior_drawdown_floor, "prior_drawdown_floor")
        if self.prior_account_failed is not None and type(self.prior_account_failed) is not bool:
            raise ValueError("prior_account_failed must be a boolean")
        if self.prior_session_blocked is not None and type(self.prior_session_blocked) is not bool:
            raise ValueError("prior_session_blocked must be a boolean")
        if self.blocked_session_id is not None and not isinstance(self.blocked_session_id, str):
            raise ValueError("blocked_session_id must be a string")
        if self.exposures is not None and (not isinstance(self.exposures, tuple) or any(not isinstance(v, ExposurePosition) for v in self.exposures)):
            raise ValueError("exposures must be an immutable tuple")
        if self.payout_cycle is not None and not isinstance(self.payout_cycle, PayoutCycleSnapshot):
            raise ValueError("invalid payout_cycle")
        if self.stage is not None and not isinstance(self.stage, AccountStage):
            raise ValueError("stage must be an AccountStage")
        for name in ("contracts_open", "contracts_traded", "trading_days", "prior_payout_count"):
            _nonnegative(getattr(self, name), name)
        for name in (
            "starting_balance", "current_balance", "current_equity", "realized_pnl",
            "unrealized_pnl", "daily_pnl", "highest_balance", "highest_equity",
            "highest_end_of_day_balance", "best_day_profit", "total_profit", "withdrawals"
        ):
            _money(getattr(self, name), name)


@dataclass(frozen=True)
class PayoutRequest:
    amount: Decimal

    def __post_init__(self) -> None:
        _money(self.amount, "payout amount", positive=True)


@dataclass(frozen=True)
class RuleEvaluationResult:
    eligible: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: tuple[tuple[str, Decimal | int | bool | None], ...]
    profile_identity: str
    rule_version: str

    def metric(self, name: str) -> Decimal | int | bool | None:
        return dict(self.metrics).get(name)
