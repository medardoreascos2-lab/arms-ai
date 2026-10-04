"""Read-only, aggregate-only Product administration projection."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.analytics_events import ProductAnalyticsTarget
from backend.product.billing import BillingStatus


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class ProductServiceHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class MembershipStateAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: BillingStatus
    count: int = Field(ge=0)


class FeatureUsageAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    feature: ProductAnalyticsTarget
    uses: int = Field(ge=0)
    unique_users: int = Field(ge=0)


class ServiceHealthAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    service_id: str = Field(pattern=_SAFE_ID)
    state: ProductServiceHealth


class ProductAdminAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    alert_reference: str = Field(pattern=_SAFE_ID)
    severity: Literal["INFO", "WATCH", "CRITICAL"]
    category: Literal["CAPACITY", "SERVICE_HEALTH", "MEMBERSHIP", "PRIVACY"]


class ReadOnlyProductAdminProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    generated_at: datetime
    beta_user_count: int = Field(ge=0)
    membership_states: tuple[MembershipStateAggregate, ...]
    feature_usage: tuple[FeatureUsageAggregate, ...]
    service_health: tuple[ServiceHealthAggregate, ...]
    alerts: tuple[ProductAdminAlert, ...]
    read_only: Literal[True] = True
    trading_mutation_authorized: Literal[False] = False
    financial_mutation_authorized: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def generated_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("generated_at must be UTC")
        return value