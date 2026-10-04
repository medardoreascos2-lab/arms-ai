"""R82D local-first model policy tests."""

import pytest

from backend.medar.model_policy import (
    ModelAccessPolicy,
    PrivacyClass,
    default_model_policy,
    evaluate_model_access,
)


def test_sensitive_and_restricted_data_default_toward_local_models():
    assert default_model_policy(PrivacyClass.SENSITIVE) is ModelAccessPolicy.LOCAL_FIRST
    assert default_model_policy(PrivacyClass.RESTRICTED) is ModelAccessPolicy.LOCAL_ONLY

    restricted = evaluate_model_access(PrivacyClass.RESTRICTED)
    assert restricted.local_only is True
    assert restricted.remote_allowed is False
    assert restricted.external_call_authorized is False


def test_remote_policy_never_itself_authorizes_external_call():
    decision = evaluate_model_access(
        PrivacyClass.PUBLIC,
        ModelAccessPolicy.REMOTE_REQUIRED,
    )

    assert decision.remote_required is True
    assert decision.remote_allowed is True
    assert decision.external_call_authorized is False


def test_restricted_data_cannot_be_overridden_to_remote():
    with pytest.raises(ValueError, match="LOCAL_ONLY"):
        evaluate_model_access(PrivacyClass.RESTRICTED, ModelAccessPolicy.REMOTE_ALLOWED)
