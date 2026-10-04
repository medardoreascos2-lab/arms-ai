"""P106C explicit onboarding memory consent tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.onboarding import (
    OnboardingMemoryConsent,
    OnboardingStatus,
    OnboardingStep,
    ProductOnboardingState,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def state(**overrides):
    body = {
        "onboarding_id": "synthetic-onboarding-1",
        "tenant_id": "synthetic-tenant-1",
        "user_id": "synthetic-user-1",
        "status": OnboardingStatus.IN_PROGRESS,
        "current_step": OnboardingStep.MEMORY_CONSENT,
        "completed_steps": (
            OnboardingStep.WELCOME,
            OnboardingStep.GOALS,
            OnboardingStep.FINANCIAL_EXPECTATIONS,
        ),
        "version": 4,
        "created_at": NOW,
        "updated_at": NOW,
    }
    body.update(overrides)
    return ProductOnboardingState(**body)


def test_memory_consent_choices_match_contract_exactly():
    assert [item.value for item in OnboardingMemoryConsent] == [
        "SESSION_ONLY", "ALLOW_LOW_SENSITIVITY",
        "REVIEW_BEFORE_SAVE", "DO_NOT_SAVE",
    ]


def test_no_memory_consent_is_forced_or_inferred():
    value = state()
    assert value.memory_consent is None
    assert value.memory_consent_confirmed is False


@pytest.mark.parametrize("choice", list(OnboardingMemoryConsent))
def test_each_memory_consent_choice_requires_explicit_confirmation(choice):
    value = state(
        memory_consent=choice,
        memory_consent_confirmed=True,
    )
    assert value.memory_consent is choice
    assert value.memory_consent_confirmed is True


def test_consent_and_confirmation_cannot_disagree():
    with pytest.raises(ValidationError):
        state(memory_consent="SESSION_ONLY")
    with pytest.raises(ValidationError):
        state(memory_consent_confirmed=True)
    with pytest.raises(ValidationError):
        state(
            memory_consent="ALLOW_HIGH_SENSITIVITY",
            memory_consent_confirmed=True,
        )
