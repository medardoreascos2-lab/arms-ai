"""Immutable, identified account snapshots for multi-account rule evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json

from .models_v1 import (
    AccountSnapshot, AccountStage, ExposurePosition, PayoutCycleSnapshot,
)


def _canonical(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value.normalize())
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {
            item.name: _canonical(getattr(value, item.name))
            for item in fields(value)
            if item.name != "content_hash"
        }
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    return value


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


@dataclass(frozen=True)
class PropFirmAccountSnapshot:
    """Account identity plus the exact rule-state observation supplied by a caller.

    The model stores no broker handle and performs no recovery, trading, payout,
    or persistence action. Missing optional rule inputs remain missing so the
    rule engine can fail closed instead of receiving inferred values.
    """

    account_id: str
    firm_id: str
    program_id: str
    profile_version: str
    stage: AccountStage
    account_size: Decimal
    captured_at: datetime
    data_source: str
    simulated: bool
    state: AccountSnapshot
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        for name in (
            "account_id", "firm_id", "program_id", "profile_version", "data_source",
        ):
            _text(getattr(self, name), name)
        if not isinstance(self.stage, AccountStage) or self.stage == AccountStage.UNKNOWN:
            raise ValueError("stage must be a known AccountStage")
        if (not isinstance(self.account_size, Decimal)
                or not self.account_size.is_finite() or self.account_size <= 0):
            raise ValueError("account_size must be a positive finite Decimal")
        if (not isinstance(self.captured_at, datetime)
                or self.captured_at.tzinfo is None
                or self.captured_at.utcoffset() is None):
            raise ValueError("captured_at must be timezone-aware")
        if type(self.simulated) is not bool:
            raise ValueError("simulated must be a boolean")
        if not isinstance(self.state, AccountSnapshot):
            raise ValueError("state must be an AccountSnapshot")
        if self.state.stage != self.stage:
            raise ValueError("snapshot stage does not match account identity")
        if self.state.as_of != self.captured_at:
            raise ValueError("snapshot as_of does not match captured_at")
        if self.state.prior_session_blocked is False and self.state.blocked_session_id is not None:
            raise ValueError("unblocked session cannot carry a blocked_session_id")

        payload = json.dumps(_canonical(self), sort_keys=True, separators=(",", ":"))
        object.__setattr__(
            self, "content_hash", hashlib.sha256(payload.encode("utf-8")).hexdigest()
        )

    @property
    def balance(self) -> Decimal | None:
        return self.state.current_balance

    @property
    def equity(self) -> Decimal | None:
        return self.state.current_equity

    @property
    def realized_pnl(self) -> Decimal | None:
        return self.state.realized_pnl

    @property
    def unrealized_pnl(self) -> Decimal | None:
        return self.state.unrealized_pnl

    @property
    def daily_pnl(self) -> Decimal | None:
        return self.state.daily_pnl

    @property
    def highest_balance(self) -> Decimal | None:
        return self.state.highest_balance

    @property
    def highest_equity(self) -> Decimal | None:
        return self.state.highest_equity

    @property
    def highest_end_of_day_balance(self) -> Decimal | None:
        return self.state.highest_end_of_day_balance

    @property
    def open_exposure(self) -> tuple[ExposurePosition, ...] | None:
        return self.state.exposures

    @property
    def trading_days(self) -> int | None:
        return self.state.trading_days

    @property
    def winning_days(self) -> int | None:
        cycle = self.state.payout_cycle
        return cycle.winning_days_since_last_payout if cycle is not None else None

    @property
    def best_day_profit(self) -> Decimal | None:
        return self.state.best_day_profit

    @property
    def profit_since_payout(self) -> Decimal | None:
        cycle = self.state.payout_cycle
        return cycle.profit_since_last_payout if cycle is not None else None

    @property
    def payout_cycle(self) -> PayoutCycleSnapshot | None:
        return self.state.payout_cycle

    @property
    def hard_breach_state(self) -> bool | None:
        return self.state.prior_account_failed

    @property
    def session_block_state(self) -> bool | None:
        return self.state.prior_session_blocked

    def to_rule_snapshot(self) -> AccountSnapshot:
        """Return the immutable rule snapshot without transforming any value."""
        return self.state
