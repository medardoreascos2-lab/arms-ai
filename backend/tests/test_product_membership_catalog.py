"""P108A Product membership catalog tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.product.membership_catalog import (
    ConfigurablePlanPrice,
    ProductPlanCatalog,
    ProductPlanCatalogEntry,
    ProductPlanId,
    configurable_product_plan_catalog,
)


def test_catalog_contains_four_contract_plans_with_nonfinal_prices():
    catalog = configurable_product_plan_catalog()
    assert [item.plan_id.value for item in catalog.plans] == [
        "FREE", "PRO", "PREMIUM", "ELITE",
    ]
    assert all(item.price.amount is None for item in catalog.plans)
    assert all(item.price.final is False for item in catalog.plans)
    assert all(item.purchasable is False for item in catalog.plans)
    assert all(item.payment_provider_connected is False for item in catalog.plans)


def test_configurable_price_can_be_modeled_without_becoming_final_or_purchasable():
    entry = ProductPlanCatalogEntry(
        plan_id="PRO",
        display_name="Pro",
        description="Synthetic price configuration.",
        price=ConfigurablePlanPrice(amount=Decimal("25.00")),
    )
    assert entry.price.amount == Decimal("25.00")
    assert entry.price.final is False
    assert entry.purchasable is False
    with pytest.raises(ValidationError):
        ProductPlanCatalogEntry.model_validate({
            **entry.model_dump(), "purchasable": True,
        })


def test_catalog_rejects_missing_duplicate_and_unknown_plans():
    catalog = configurable_product_plan_catalog()
    with pytest.raises(ValidationError):
        ProductPlanCatalog(plans=catalog.plans[:-1])
    with pytest.raises(ValidationError):
        ProductPlanCatalog(plans=(
            catalog.plans[0], catalog.plans[0],
            catalog.plans[2], catalog.plans[3],
        ))
    with pytest.raises(ValidationError):
        ConfigurablePlanPrice(amount=Decimal("-1"))
