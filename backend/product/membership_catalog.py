"""Product membership catalog with configurable, explicitly non-final prices."""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductPlanId(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    PREMIUM = "PREMIUM"
    ELITE = "ELITE"


class BillingInterval(str, Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class ConfigurablePlanPrice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    interval: BillingInterval = BillingInterval.MONTHLY
    final: Literal[False] = False


class ProductPlanCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    plan_id: ProductPlanId
    display_name: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=256)
    price: ConfigurablePlanPrice
    purchasable: Literal[False] = False
    payment_provider_connected: Literal[False] = False


class ProductPlanCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plans: tuple[ProductPlanCatalogEntry, ...]

    @field_validator("plans")
    @classmethod
    def require_exact_unique_catalog(
        cls, value: tuple[ProductPlanCatalogEntry, ...],
    ) -> tuple[ProductPlanCatalogEntry, ...]:
        ids = [item.plan_id for item in value]
        if len(ids) != len(set(ids)) or set(ids) != set(ProductPlanId):
            raise ValueError("catalog must contain each Product plan exactly once")
        return value


def configurable_product_plan_catalog() -> ProductPlanCatalog:
    descriptions = {
        ProductPlanId.FREE: "Core Product preview.",
        ProductPlanId.PRO: "Expanded Product tools.",
        ProductPlanId.PREMIUM: "Premium intelligence foundation.",
        ProductPlanId.ELITE: "Highest configurable Product tier.",
    }
    return ProductPlanCatalog(plans=tuple(
        ProductPlanCatalogEntry(
            plan_id=plan_id,
            display_name=plan_id.value.title(),
            description=descriptions[plan_id],
            price=ConfigurablePlanPrice(),
        )
        for plan_id in ProductPlanId
    ))
