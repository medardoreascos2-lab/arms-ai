"""Configurable closed-beta capacity policy."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.product.beta_access import BetaAccessRecord, BetaAccessStatus


class BetaCapacityState(str, Enum):
    BELOW_TARGET = "BELOW_TARGET"
    WITHIN_TARGET = "WITHIN_TARGET"
    AT_CAPACITY = "AT_CAPACITY"


class BetaCapacityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_min_users: int = Field(default=10, ge=1)
    target_max_users: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def valid_range(self) -> "BetaCapacityPolicy":
        if self.target_max_users < self.target_min_users:
            raise ValueError("target maximum must be at least target minimum")
        return self


class BetaCapacityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    active_users: int = Field(ge=0)
    state: BetaCapacityState
    admission_available: bool
    remaining_slots: int = Field(ge=0)


def evaluate_beta_capacity(
    records: tuple[BetaAccessRecord, ...],
    policy: BetaCapacityPolicy = BetaCapacityPolicy(),
) -> BetaCapacityDecision:
    active = sum(record.status == BetaAccessStatus.ACTIVE for record in records)
    if active >= policy.target_max_users:
        state = BetaCapacityState.AT_CAPACITY
    elif active < policy.target_min_users:
        state = BetaCapacityState.BELOW_TARGET
    else:
        state = BetaCapacityState.WITHIN_TARGET
    return BetaCapacityDecision(
        active_users=active,
        state=state,
        admission_available=active < policy.target_max_users,
        remaining_slots=max(0, policy.target_max_users - active),
    )