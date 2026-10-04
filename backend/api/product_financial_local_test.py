"""Standalone Product financial application for explicit local synthetic testing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from fastapi import FastAPI

from backend.api.product_financial_api import create_local_test_product_financial_router
from backend.memberships import MembershipReadAdapter
from backend.product.customer_session import LocalSyntheticSessionProvider
from backend.product.financial_authorization import CustomerFinancialScopeProvider
from backend.product.financial_models import (
    FinancialReadStatus,
    ProductFinancialDegradedResponse,
)
from backend.product.synthetic_financial_provider import LocalSyntheticFinancialProvider


PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED = "PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED"


@dataclass(frozen=True)
class ProductFinancialLocalTestConfig:
    enabled: bool = False
    environment: str = "DISABLED"

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("local test enabled must be boolean")
        if self.enabled and self.environment not in {"LOCAL", "TEST"}:
            raise ValueError("Product financial data may mount only in LOCAL or TEST")

    @classmethod
    def from_environment(cls, values: Mapping[str, str]) -> ProductFinancialLocalTestConfig:
        enabled = values.get(PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED, "false")
        if enabled not in {"true", "false"}:
            raise ValueError("PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED must be true or false")
        return cls(
            enabled=enabled == "true",
            environment=values.get("PRODUCT_FINANCIAL_ENVIRONMENT", "DISABLED"),
        )


def create_local_test_product_financial_app(
    *,
    config: ProductFinancialLocalTestConfig = ProductFinancialLocalTestConfig(),
    session_provider: LocalSyntheticSessionProvider | None = None,
    membership_adapter: MembershipReadAdapter | None = None,
    scope_provider: CustomerFinancialScopeProvider | None = None,
    financial_provider: LocalSyntheticFinancialProvider | None = None,
    clock: Callable[[], datetime] | None = None,
    maximum_freshness_seconds: int = 300,
) -> FastAPI:
    app = FastAPI(title="ARMS Product Financial LOCAL SYNTHETIC TEST ONLY")
    app.state.product_financial_local_test_enabled = config.enabled
    if not config.enabled:
        def unavailable() -> ProductFinancialDegradedResponse:
            return ProductFinancialDegradedResponse(
                status=FinancialReadStatus.INTEGRATION_PENDING
            )
        for suffix in ("overview", "trading", "portfolio", "coach", "shadow"):
            app.get(f"/product/financial/{suffix}")(unavailable)
        return app
    if not isinstance(session_provider, LocalSyntheticSessionProvider):
        raise TypeError("local synthetic customer session provider required")
    if membership_adapter is None or scope_provider is None:
        raise TypeError("local membership and financial scope providers required")
    if not isinstance(financial_provider, LocalSyntheticFinancialProvider):
        raise TypeError("local synthetic financial provider required")
    app.include_router(create_local_test_product_financial_router(
        session_provider=session_provider,
        membership_adapter=membership_adapter,
        scope_provider=scope_provider,
        financial_provider=financial_provider,
        clock=clock,
        maximum_freshness_seconds=maximum_freshness_seconds,
    ))
    return app
