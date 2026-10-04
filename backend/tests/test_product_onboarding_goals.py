"""P106B optional onboarding goal selection tests."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.product.onboarding import (
    OnboardingGoal,
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
        "current_step": OnboardingStep.GOALS,
        "completed_steps": (OnboardingStep.WELCOME,),
        "version": 2,
        "created_at": NOW,
        "updated_at": NOW,
    }
    body.update(overrides)
    return ProductOnboardingState(**body)


def test_goal_catalog_matches_contract_exactly():
    assert [item.value for item in OnboardingGoal] == [
        "TRADING", "INVESTING", "PORTFOLIO", "BUSINESS",
        "LEARNING", "PERSONAL_ASSISTANT",
    ]


def test_goals_are_optional_and_require_explicit_confirmation():
    empty = state()
    assert empty.selected_goals == ()
    assert empty.goals_confirmed is False
    confirmed_empty = state(goals_confirmed=True)
    assert confirmed_empty.selected_goals == ()
    selected = state(
        selected_goals=(OnboardingGoal.LEARNING, OnboardingGoal.PERSONAL_ASSISTANT),
        goals_confirmed=True,
    )
    assert selected.selected_goals == (
        OnboardingGoal.LEARNING, OnboardingGoal.PERSONAL_ASSISTANT,
    )


def test_unknown_and_duplicate_goals_are_rejected_without_inference():
    with pytest.raises(ValidationError):
        state(selected_goals=("HEALTH_DIAGNOSIS",), goals_confirmed=True)
    with pytest.raises(ValidationError):
        state(selected_goals=(
            OnboardingGoal.TRADING, OnboardingGoal.TRADING,
        ), goals_confirmed=True)
