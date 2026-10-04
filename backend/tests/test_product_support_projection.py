"""P116B default-deny Product support projection tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.support_projection import (
    ProductSupportProjection,
    SupportAccountMetadata,
    SupportViewAuthorization,
    create_support_projection,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)
METADATA = SupportAccountMetadata(
    account_reference="account-opaque-1",
    tenant_reference="tenant-opaque-1",
    created_at=NOW,
)
AUTHORIZATION = SupportViewAuthorization(
    request_id="support-request-1", operator_id="support-operator-1", authorized=True,
)


def test_support_projection_requires_explicit_read_only_authorization():
    with pytest.raises(PermissionError):
        create_support_projection(
            authorization=None, account_metadata=METADATA, membership_state="ACTIVE",
            error_reference="error-1", session_status="ACTIVE",
        )
    value = create_support_projection(
        authorization=AUTHORIZATION, account_metadata=METADATA, membership_state="ACTIVE",
        error_reference="error-1", session_status="ACTIVE",
    )
    assert value.account_metadata == METADATA
    assert value.membership_state == "ACTIVE"
    assert value.error_reference == "error-1"
    assert value.session_status == "ACTIVE"
    assert value.read_only is True


def test_support_view_structurally_denies_sensitive_content():
    value = create_support_projection(
        authorization=AUTHORIZATION, account_metadata=METADATA, membership_state="ACTIVE",
        error_reference=None, session_status="ACTIVE",
    )
    assert value.sensitive_content_included is False
    assert value.financial_details_included is False
    forbidden = {
        "conversation_content": "private",
        "memory_content": "private",
        "financial_details": {"balance": 1},
        "health_data": "private",
    }
    for field, content in forbidden.items():
        with pytest.raises(ValidationError):
            ProductSupportProjection.model_validate({**value.model_dump(), field: content})
    with pytest.raises(ValidationError):
        SupportViewAuthorization(
            request_id="request-2", operator_id="operator-2", authorized=False,
        )