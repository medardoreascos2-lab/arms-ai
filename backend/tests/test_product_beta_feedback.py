"""P111C closed-beta feedback privacy tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.beta_feedback import (
    BetaFeedback,
    BetaFeedbackType,
    LocalSqliteBetaFeedbackStore,
)


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def feedback(tenant="tenant-a", user="user-1"):
    return BetaFeedback(
        feedback_id=f"feedback-{tenant}-{user}", tenant_id=tenant, user_id=user,
        feedback_type="BUG", surface="HOME", error_reference="error-123",
        occurred_at=NOW,
    )


def test_feedback_types_match_contract():
    assert {item.value for item in BetaFeedbackType} == {
        "BUG", "FEATURE_REQUEST", "CONFUSING_UX", "WRONG_ANSWER",
        "USEFUL_ANSWER", "BILLING_FEEDBACK",
    }


def test_private_content_is_structurally_disabled():
    value = feedback()
    assert value.private_content_included is False
    assert value.comment is None
    with pytest.raises(ValidationError):
        BetaFeedback.model_validate({**value.model_dump(), "comment": "private text"})
    with pytest.raises(ValidationError):
        BetaFeedback.model_validate({**value.model_dump(), "private_content_included": True})
    with pytest.raises(ValidationError):
        BetaFeedback.model_validate({**value.model_dump(), "answer_content": "private"})


def test_feedback_store_is_tenant_and_user_scoped():
    store = LocalSqliteBetaFeedbackStore()
    store.append(feedback())
    store.append(feedback("tenant-b", "user-1"))
    assert len(store.list_for_user("tenant-a", "user-1")) == 1
    assert store.list_for_user("tenant-a", "missing") == ()