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


def _aware(value: datetime | None, name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True)
class DrawdownPolicy:
    model: DrawdownModel
    maximum_loss: Decimal | None = None
    breach_basis: ValueBasis | None = None
    floor_cap: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, DrawdownModel):
            raise ValueError("drawdown model must be a DrawdownModel")
        if self.breach_basis is not None and not isinstance(self.breach_basis, ValueBasis):
            raise ValueError("breach_basis must be a ValueBasis")
        if self.model == DrawdownModel.NONE:
            if any(v is not None for v in (self.maximum_loss, self.breach_basis, self.floor_cap)):
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

    def __post_init__(self) -> None:
        _money(self.limit, "daily loss limit", positive=True)


@dataclass(frozen=True)
class ContractLimitPolicy:
    maximum_open: int
    maximum_traded: int | None = None

    def __post_init__(self) -> None:
        _nonnegative(self.maximum_open, "maximum_open")
        _nonnegative(self.maximum_traded, "maximum_traded")
        if self.maximum_open == 0:
            raise ValueError("maximum_open must be positive")
        if self.maximum_traded == 0:
            raise ValueError("maximum_traded must be positive")


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

    def __post_init__(self) -> None:
        if self.calculation_mode is not None and not isinstance(self.calculation_mode, ConsistencyMode):
            raise ValueError("calculation_mode must be a ConsistencyMode")
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

    def __post_init__(self) -> None:
        _nonnegative(self.minimum_trading_days, "minimum_trading_days")
        _nonnegative(self.minimum_days_since_prior_payout, "minimum_days_since_prior_payout")
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
            self.consistency_required, self.minimum_days_since_prior_payout
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
    config_hash: str = field(init=False)

    def __post_init__(self) -> None:
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
        _money(self.starting_balance, "starting_balance", positive=True)
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

    def __post_init__(self) -> None:
        _aware(self.as_of, "as_of")
        _aware(self.last_payout_at, "last_payout_at")
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
