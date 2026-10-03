"""Strict transport models for read-only prop-firm policy evaluation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt

from backend.prop_firms import (
    AccountSnapshot,
    AccountStage,
    ExposurePosition,
    PayoutCycleSnapshot,
    PayoutRequest,
    PropFirmAccountSnapshot,
)


def _reject_float(value: Any) -> Any:
    if isinstance(value, float):
        raise ValueError("decimal values must be encoded as strings or integers")
    return value


ExactDecimal = Annotated[Decimal, BeforeValidator(_reject_float)]


class PolicyInputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExposurePositionInput(PolicyInputModel):
    instrument: str
    quantity: StrictInt
    product_group: str | None = None

    def to_domain(self) -> ExposurePosition:
        return ExposurePosition(
            instrument=self.instrument,
            quantity=self.quantity,
            product_group=self.product_group,
        )


class PayoutCycleSnapshotInput(PolicyInputModel):
    cycle_id: str | None = None
    payout_count: StrictInt | None = None
    last_payout_at: datetime | None = None
    profit_since_last_payout: ExactDecimal | None = None
    winning_days_since_last_payout: StrictInt | None = None
    trading_days_since_last_payout: StrictInt | None = None
    current_cycle_start: datetime | None = None
    withdrawals_total: ExactDecimal | None = None
    requested_payout_amount: ExactDecimal | None = None
    best_day_profit_since_last_payout: ExactDecimal | None = None
    qualifying_days_since_last_payout: StrictInt | None = None
    qualifying_day_profit_threshold: ExactDecimal | None = None

    def to_domain(self) -> PayoutCycleSnapshot:
        return PayoutCycleSnapshot(**self.model_dump())


class AccountSnapshotInput(PolicyInputModel):
    as_of: datetime
    account_started_at: datetime | None = None
    stage: AccountStage
    starting_balance: ExactDecimal | None = None
    current_balance: ExactDecimal | None = None
    current_equity: ExactDecimal | None = None
    realized_pnl: ExactDecimal | None = None
    unrealized_pnl: ExactDecimal | None = None
    daily_pnl: ExactDecimal | None = None
    highest_balance: ExactDecimal | None = None
    highest_equity: ExactDecimal | None = None
    highest_end_of_day_balance: ExactDecimal | None = None
    prior_end_of_day_balance: ExactDecimal | None = None
    contracts_open: StrictInt | None = None
    working_orders: StrictInt | None = None
    contracts_traded: StrictInt | None = None
    trading_days: StrictInt | None = None
    best_day_profit: ExactDecimal | None = None
    total_profit: ExactDecimal | None = None
    withdrawals: ExactDecimal | None = None
    prior_payout_count: StrictInt | None = None
    last_payout_at: datetime | None = None
    session_id: str | None = None
    daily_pnl_session_id: str | None = None
    prior_session_blocked: StrictBool | None = None
    blocked_session_id: str | None = None
    session_ends_at: datetime | None = None
    trading_day_ends_at: datetime | None = None
    prior_drawdown_floor: ExactDecimal | None = None
    prior_account_failed: StrictBool | None = None
    exposures: tuple[ExposurePositionInput, ...] | None = None
    payout_cycle: PayoutCycleSnapshotInput | None = None
    activity_window_days: StrictInt | None = None
    qualifying_activity_days: StrictInt | None = None
    activity_day_profit_threshold: ExactDecimal | None = None

    def to_domain(self) -> AccountSnapshot:
        values = self.model_dump(exclude={"exposures", "payout_cycle"})
        values["exposures"] = (
            None
            if self.exposures is None
            else tuple(item.to_domain() for item in self.exposures)
        )
        values["payout_cycle"] = (
            None if self.payout_cycle is None else self.payout_cycle.to_domain()
        )
        return AccountSnapshot(**values)


class PropFirmAccountSnapshotInput(PolicyInputModel):
    account_id: str
    firm_id: str
    program_id: str
    profile_version: str
    stage: AccountStage
    account_size: ExactDecimal
    captured_at: datetime
    data_source: str
    simulated: StrictBool
    state: AccountSnapshotInput

    def to_domain(self) -> PropFirmAccountSnapshot:
        return PropFirmAccountSnapshot(
            account_id=self.account_id,
            firm_id=self.firm_id,
            program_id=self.program_id,
            profile_version=self.profile_version,
            stage=self.stage,
            account_size=self.account_size,
            captured_at=self.captured_at,
            data_source=self.data_source,
            simulated=self.simulated,
            state=self.state.to_domain(),
        )


class PayoutRequestInput(PolicyInputModel):
    amount: ExactDecimal

    def to_domain(self) -> PayoutRequest:
        return PayoutRequest(amount=self.amount)


class AccountPolicyEvaluationRequest(PolicyInputModel):
    snapshot: PropFirmAccountSnapshotInput
    payout_request: PayoutRequestInput | None = None
    require_current_sources: StrictBool = True


class MultiAccountPolicyEvaluationRequest(PolicyInputModel):
    snapshots: tuple[PropFirmAccountSnapshotInput, ...]
    payout_requests: dict[str, PayoutRequestInput] = Field(default_factory=dict)
    require_current_sources: StrictBool = True
