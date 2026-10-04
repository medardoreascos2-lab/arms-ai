"""Provider-neutral Product billing foundation with no payment authority."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.product.membership_catalog import ProductPlanId


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class BillingStatus(str, Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    INCOMPLETE = "INCOMPLETE"


class BillingCustomer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    billing_customer_id: str = Field(pattern=_SAFE_ID)
    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    provider: Literal["NONE", "LOCAL_SYNTHETIC"] = "NONE"
    payment_method_attached: Literal[False] = False
    charge_authorized: Literal[False] = False


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: ProductPlanId
    catalog_version: str = Field(pattern=_SAFE_ID)
    price_final: Literal[False] = False
    purchasable: Literal[False] = False


class Trial(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    starts_at: datetime
    ends_at: datetime

    @field_validator("starts_at", "ends_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("trial timestamps must be UTC")
        return value

    @model_validator(mode="after")
    def positive_window(self) -> Trial:
        if self.ends_at <= self.starts_at:
            raise ValueError("trial must have a positive duration")
        return self


class InvoiceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    invoice_reference: str = Field(pattern=_SAFE_ID)
    provider: Literal["LOCAL_SYNTHETIC"]
    amount: str = Field(pattern=r"^[0-9]+(?:\.[0-9]{2})$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    charged: Literal[False] = False


class Subscription(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subscription_id: str = Field(pattern=_SAFE_ID)
    billing_customer_id: str = Field(pattern=_SAFE_ID)
    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)
    plan: Plan
    status: BillingStatus
    trial: Trial | None = None
    invoice_references: tuple[InvoiceReference, ...] = ()
    version: int = Field(ge=1)
    payment_provider_connected: Literal[False] = False
    charge_authorized: Literal[False] = False

    @model_validator(mode="after")
    def trial_matches_status(self) -> Subscription:
        if self.status == BillingStatus.TRIAL and self.trial is None:
            raise ValueError("trial status requires trial dates")
        return self
