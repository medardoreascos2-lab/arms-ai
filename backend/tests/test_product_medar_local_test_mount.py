"""P102A4 local mount requires explicit configuration and synthetic sessions."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.product_medar_local_test import (
    ProductMedarLocalTestConfig,
    create_local_test_product_medar_app,
)
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


class Memberships:
    def get_membership(self, tenant_id, user_id):
        return None


def provider():
    return LocalSyntheticSessionProvider((synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
    ),))


def test_local_mount_is_disabled_by_default_and_has_no_route():
    app = create_local_test_product_medar_app()
    assert app.state.product_medar_local_test_enabled is False
    assert "/product/medar/conversations" not in app.openapi()["paths"]
    client = TestClient(app, client=("127.0.0.1", 50000))
    assert client.post("/product/medar/conversations", json={}).status_code == 404


def test_enabled_local_mount_requires_synthetic_provider_and_explicit_mode():
    with pytest.raises(ValueError, match="LOCAL or TEST"):
        ProductMedarLocalTestConfig(enabled=True, environment="PRODUCTION")
    with pytest.raises(TypeError, match="synthetic"):
        create_local_test_product_medar_app(config=ProductMedarLocalTestConfig(True, "LOCAL"))
    config = ProductMedarLocalTestConfig.from_environment({
        "PRODUCT_MEDAR_LOCAL_TEST_ENABLED": "true",
        "PRODUCT_MEDAR_ENVIRONMENT": "TEST",
    })
    app = create_local_test_product_medar_app(
        config=config, session_provider=provider(),
        membership_adapter=Memberships(), clock=lambda: NOW,
    )
    assert app.state.product_medar_local_test_enabled is True
    assert "/product/medar/conversations" in app.openapi()["paths"]
    response = TestClient(app, client=("127.0.0.1", 50000)).post(
        "/product/medar/conversations",
        json={"request_id": "r1", "conversation_id": "c1", "message": "hello"},
        headers={"X-ARMS-Local-Test-Session": "unknown"},
    )
    assert response.json()["status"] == "PERMISSION_DENIED"


def test_invalid_flag_is_rejected_and_false_does_not_mount():
    with pytest.raises(ValueError, match="true or false"):
        ProductMedarLocalTestConfig.from_environment({
            "PRODUCT_MEDAR_LOCAL_TEST_ENABLED": "yes",
        })
    config = ProductMedarLocalTestConfig.from_environment({})
    assert config.enabled is False
    assert "/product/medar/conversations" not in create_local_test_product_medar_app(config=config).openapi()["paths"]
