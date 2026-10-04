"""P106A durable Product onboarding state tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.product.notification_store import NotificationScope
from backend.product.onboarding import (
    LocalSqliteOnboardingStore,
    OnboardingStatus,
    OnboardingStep,
    ProductOnboardingState,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
SCOPE = NotificationScope("synthetic-tenant-1", "synthetic-user-1")
OTHER = NotificationScope("synthetic-tenant-1", "synthetic-user-2")


def state(**overrides):
    body = {
        "onboarding_id": "synthetic-onboarding-1",
        "tenant_id": SCOPE.tenant_id,
        "user_id": SCOPE.user_id,
        "status": OnboardingStatus.NOT_STARTED,
        "current_step": OnboardingStep.WELCOME,
        "completed_steps": (),
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    body.update(overrides)
    return ProductOnboardingState(**body)


def test_statuses_and_steps_match_contract_exactly():
    assert {item.value for item in OnboardingStatus} == {
        "NOT_STARTED", "IN_PROGRESS", "COMPLETED", "SKIPPED_OPTIONAL", "BLOCKED",
    }
    assert [item.value for item in OnboardingStep] == [
        "WELCOME", "GOALS", "FINANCIAL_EXPECTATIONS", "MEMORY_CONSENT",
        "NOTIFICATION_PREFS", "PRIVACY", "DONE",
    ]


def test_state_rejects_inconsistent_completion_blocking_and_timestamps():
    with pytest.raises(ValidationError):
        state(status="COMPLETED")
    with pytest.raises(ValidationError):
        state(status="BLOCKED")
    with pytest.raises(ValidationError):
        state(
            status="IN_PROGRESS",
            blocked_reason="unexpected",
        )
    with pytest.raises(ValidationError):
        state(updated_at=NOW - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        state(created_at=datetime(2026, 10, 4, 12))


def test_store_is_scoped_resumable_and_persistent(tmp_path):
    path = str(tmp_path / "onboarding.sqlite3")
    store = LocalSqliteOnboardingStore(path, environment="LOCAL_TEST_ONLY")
    initial = state()
    store.save(SCOPE, initial, expected_version=None)
    progress = state(
        status="IN_PROGRESS",
        current_step="GOALS",
        completed_steps=("WELCOME",),
        version=2,
        updated_at=NOW + timedelta(minutes=1),
    )
    store.save(SCOPE, progress, expected_version=1)
    assert store.get(SCOPE) == progress
    assert store.get(OTHER) is None
    store.close()

    reopened = LocalSqliteOnboardingStore(path, environment="DEVELOPMENT")
    assert reopened.get(SCOPE) == progress
    reopened.close()


def test_store_rejects_wrong_scope_stale_write_and_identity_change(tmp_path):
    store = LocalSqliteOnboardingStore(
        str(tmp_path / "onboarding.sqlite3"),
        environment="LOCAL_TEST_ONLY",
    )
    initial = state()
    with pytest.raises(PermissionError):
        store.save(OTHER, initial, expected_version=None)
    store.save(SCOPE, initial, expected_version=None)
    with pytest.raises(RuntimeError):
        store.save(SCOPE, state(version=2), expected_version=0)
    with pytest.raises(ValueError):
        store.save(SCOPE, state(
            onboarding_id="synthetic-onboarding-other",
            version=2,
            updated_at=NOW + timedelta(minutes=1),
        ), expected_version=1)
    store.close()


def test_completed_state_requires_done_and_store_rejects_production(tmp_path):
    completed = state(
        status="COMPLETED",
        current_step="DONE",
        completed_steps=tuple(OnboardingStep),
    )
    assert completed.status is OnboardingStatus.COMPLETED
    with pytest.raises(ValueError):
        LocalSqliteOnboardingStore(
            str(tmp_path / "production.sqlite3"),
            environment="PRODUCTION",
        )
