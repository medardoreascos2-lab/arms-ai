"""Separate Product MEDAR app for explicit local testing only.

The frozen/default ARMS API never imports or mounts this app.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Mapping

from fastapi import FastAPI

from backend.api.product_medar_api import create_local_test_product_medar_router
from backend.memberships import MembershipReadAdapter
from backend.product.customer_session import LocalSyntheticSessionProvider
from backend.product.medar_adapter import ProductMedarRuntime
from backend.product.medar_usage import ProductMedarUsageGate


PRODUCT_MEDAR_LOCAL_TEST_ENABLED = "PRODUCT_MEDAR_LOCAL_TEST_ENABLED"


@dataclass(frozen=True)
class ProductMedarLocalTestConfig:
    enabled: bool = False
    environment: str = "DISABLED"

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("local test enabled must be boolean")
        if self.enabled and self.environment not in {"LOCAL", "TEST"}:
            raise ValueError("Product MEDAR may mount only in explicit LOCAL or TEST mode")

    @classmethod
    def from_environment(cls, values: Mapping[str, str]) -> ProductMedarLocalTestConfig:
        enabled = values.get(PRODUCT_MEDAR_LOCAL_TEST_ENABLED, "false")
        if enabled not in {"true", "false"}:
            raise ValueError("PRODUCT_MEDAR_LOCAL_TEST_ENABLED must be true or false")
        return cls(
            enabled=enabled == "true",
            environment=values.get("PRODUCT_MEDAR_ENVIRONMENT", "DISABLED"),
        )


def create_local_test_product_medar_app(
    *,
    config: ProductMedarLocalTestConfig = ProductMedarLocalTestConfig(),
    session_provider: LocalSyntheticSessionProvider | None = None,
    membership_adapter: MembershipReadAdapter | None = None,
    runtime: ProductMedarRuntime | None = None,
    usage_gate: ProductMedarUsageGate | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Standalone local app. Disabled state contains no Product MEDAR route."""
    if not isinstance(config, ProductMedarLocalTestConfig):
        raise TypeError("explicit local test config required")
    app = FastAPI(title="ARMS Product MEDAR LOCAL TEST ONLY")
    app.state.product_medar_local_test_enabled = config.enabled
    if not config.enabled:
        return app
    if not isinstance(session_provider, LocalSyntheticSessionProvider):
        raise TypeError("local synthetic session provider required")
    if membership_adapter is None:
        raise TypeError("local membership adapter required")
    app.include_router(create_local_test_product_medar_router(
        session_provider=session_provider,
        membership_adapter=membership_adapter,
        runtime=runtime,
        usage_gate=usage_gate,
        clock=clock,
    ))
    return app
