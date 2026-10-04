"""P107A scoped Product profile preference tests."""

import pytest
from pydantic import ValidationError

from backend.product.notification_store import NotificationScope
from backend.product.notifications import NotificationChannel
from backend.product.profile import (
    AccessibilityPreferences,
    LocalSqliteProductProfileStore,
    ProductProfilePreferences,
    ProductResponseProfile,
    ProductTheme,
)


SCOPE = NotificationScope("synthetic-tenant-1", "synthetic-user-1")
OTHER = NotificationScope("synthetic-tenant-1", "synthetic-user-2")


def profile(**overrides):
    body = {
        "tenant_id": SCOPE.tenant_id,
        "user_id": SCOPE.user_id,
        "display_name": "Synthetic Customer",
        "language": "en-US",
        "timezone": "America/New_York",
        "theme": ProductTheme.DARK,
        "accessibility": AccessibilityPreferences(
            reduced_motion=True,
            text_scale=1.2,
        ),
        "response_profile": ProductResponseProfile.BALANCED,
        "notification_defaults": (NotificationChannel.IN_APP,),
        "version": 1,
    }
    body.update(overrides)
    return ProductProfilePreferences(**body)


def test_profile_contains_all_contract_preferences_and_is_frozen():
    value = profile()
    assert value.display_name == "Synthetic Customer"
    assert value.language == "en-US"
    assert value.timezone == "America/New_York"
    assert value.theme is ProductTheme.DARK
    assert value.accessibility.reduced_motion is True
    assert value.response_profile is ProductResponseProfile.BALANCED
    assert value.notification_defaults == (NotificationChannel.IN_APP,)
    with pytest.raises(ValidationError):
        value.display_name = "Changed"


def test_profile_rejects_unknown_timezone_language_scale_and_channels():
    with pytest.raises(ValidationError):
        profile(timezone="Not/A_Real_Zone")
    with pytest.raises(ValidationError):
        profile(language="../secret")
    with pytest.raises(ValidationError):
        profile(accessibility=AccessibilityPreferences(text_scale=3))
    with pytest.raises(ValidationError):
        profile(notification_defaults=(
            NotificationChannel.EMAIL, NotificationChannel.EMAIL,
        ))


def test_profile_store_is_scoped_versioned_and_persistent(tmp_path):
    path = str(tmp_path / "profile.sqlite3")
    store = LocalSqliteProductProfileStore(path, environment="LOCAL_TEST_ONLY")
    first = profile()
    store.save(SCOPE, first, expected_version=None)
    second = profile(display_name="Updated Customer", version=2)
    store.save(SCOPE, second, expected_version=1)
    assert store.get(SCOPE) == second
    assert store.get(OTHER) is None
    with pytest.raises(PermissionError):
        store.save(OTHER, profile(version=3), expected_version=2)
    with pytest.raises(RuntimeError):
        store.save(SCOPE, profile(version=3), expected_version=1)
    store.close()

    reopened = LocalSqliteProductProfileStore(path, environment="DEVELOPMENT")
    assert reopened.get(SCOPE) == second
    reopened.close()


def test_profile_store_rejects_production_environment(tmp_path):
    with pytest.raises(ValueError):
        LocalSqliteProductProfileStore(
            str(tmp_path / "production.sqlite3"),
            environment="PRODUCTION",
        )
