"""P107B Product privacy-center boundary tests."""

import inspect

import pytest
from pydantic import ValidationError

from backend.product.privacy import (
    ConnectedServiceProjection,
    MemoryCategoryProjection,
    PrivacyRequestKind,
    PrivacyRequestSeam,
    PrivacySeamStatus,
    ProductPrivacyProjection,
    RetentionChoice,
)


def projection(**overrides):
    body = {
        "tenant_id": "synthetic-tenant-1",
        "user_id": "synthetic-user-1",
        "memory_categories": (
            MemoryCategoryProjection(
                category="PREFERENCES",
                visible=True,
                provenance="LOCAL_TEST_ONLY",
            ),
        ),
        "retention_choice": RetentionChoice.SESSION_ONLY,
        "data_export_status": PrivacySeamStatus.INTEGRATION_PENDING,
        "removal_request_status": PrivacySeamStatus.INTEGRATION_PENDING,
        "connected_services": (
            ConnectedServiceProjection(
                service_reference="synthetic-service-1",
                label="Synthetic service seam",
                status=PrivacySeamStatus.INTEGRATION_PENDING,
            ),
        ),
        "activity_history_visible": None,
    }
    body.update(overrides)
    return ProductPrivacyProjection(**body)


def test_privacy_projection_shows_all_required_seams_without_deletion_authority():
    value = projection()
    assert value.memory_categories[0].category == "PREFERENCES"
    assert value.retention_choice is RetentionChoice.SESSION_ONLY
    assert value.data_export_status is PrivacySeamStatus.INTEGRATION_PENDING
    assert value.removal_request_status is PrivacySeamStatus.INTEGRATION_PENDING
    assert value.connected_services[0].status is PrivacySeamStatus.INTEGRATION_PENDING
    assert value.activity_history_visible is None
    assert value.direct_deletion_authorized is False
    assert value.production_identity_authorized is False


def test_privacy_authority_flags_cannot_be_enabled():
    with pytest.raises(ValidationError):
        projection(direct_deletion_authorized=True)
    with pytest.raises(ValidationError):
        projection(production_identity_authorized=True)


def test_request_seam_supports_review_requests_and_has_no_delete_method():
    public = {
        name for name, item in PrivacyRequestSeam.__dict__.items()
        if not name.startswith("_") and callable(item)
    }
    assert public == {"request_review"}
    assert {item.value for item in PrivacyRequestKind} == {
        "DATA_EXPORT", "REMOVAL_REVIEW",
    }
    assert "delete" not in inspect.getsource(PrivacyRequestSeam).lower()
