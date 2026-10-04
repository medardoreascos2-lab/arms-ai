"""Provider-neutral billing adapter contract; no payment provider is connected."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.product.billing import BillingCustomer, Subscription
from backend.product.membership_catalog import ProductPlanId


_SAFE_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class BillingProviderKind(str, Enum):
    NONE = "NONE"
    STRIPE = "STRIPE"
    OTHER = "OTHER"


class BillingLifecycleAction(str, Enum):
    START_TRIAL = "START_TRIAL"
    SUBSCRIBE = "SUBSCRIBE"
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    CANCEL = "CANCEL"
    EXPIRE = "EXPIRE"


class BillingProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: BillingProviderKind = BillingProviderKind.NONE
    connected: Literal[False] = False
    supports_charges: Literal[False] = False
    external_webhooks_enabled: Literal[False] = False


class BillingScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(pattern=_SAFE_ID)
    user_id: str = Field(pattern=_SAFE_ID)


class BillingLifecycleCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: BillingLifecycleAction
    scope: BillingScope
    target_plan_id: ProductPlanId | None = None
    idempotency_key: str = Field(pattern=_SAFE_ID)
    requested_at: datetime
    charge_authorized: Literal[False] = False

    @field_validator("requested_at")
    @classmethod
    def requested_at_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("requested_at must be UTC")
        return value


@runtime_checkable
class BillingProvider(Protocol):
    """Adapter seam for metadata-only lifecycle simulation and future providers."""

    def status(self) -> BillingProviderStatus: ...

    def get_customer(self, scope: BillingScope) -> BillingCustomer | None: ...

    def get_subscription(self, scope: BillingScope) -> Subscription | None: ...

    def apply_lifecycle(self, command: BillingLifecycleCommand) -> Subscription: ...