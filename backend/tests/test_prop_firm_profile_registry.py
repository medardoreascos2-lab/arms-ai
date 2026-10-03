"""Canonical profile registry tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest

from backend.prop_firms import (
    AccountStage, AmbiguousProfileError, ProfileNotFoundError,
    ProfileSourceStatusError, PropFirmProfileRegistry, SourceStatus,
    canonical_profile_registry,
)
from backend.prop_firms.lucid_profiles import REVIEWED_AT as LUCID_REVIEWED_AT
from backend.prop_firms.topstep_profiles import (
    REVIEWED_AT as TOPSTEP_REVIEWED_AT, trading_combine_profile,
)

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_canonical_registry_contains_all_normalized_profile_families():
    registry = canonical_profile_registry()
    items = registry.list_supported_profiles(NOW)
    assert len(items) == 81
    assert {item.firm_id for item in items} == {
        "topstep", "apex", "takeprofittrader", "lucid",
    }
    assert {item.source_status for item in items} == {
        SourceStatus.CURRENT_VERIFIED,
        SourceStatus.INCOMPLETE,
        SourceStatus.SOURCE_CONFLICT,
    }
    assert all(item.config_hash and item.version for item in items)


def test_resolve_requires_exact_version_when_active_variants_are_ambiguous():
    registry = canonical_profile_registry()
    with pytest.raises(AmbiguousProfileError):
        registry.resolve_profile(
            "topstep", "trading_combine", AccountStage.EVALUATION,
            D("50000"), NOW,
        )
    resolved = registry.resolve_profile(
        "topstep", "trading_combine", AccountStage.EVALUATION,
        D("50000"), NOW, version="2026-10-03/no-dll",
    )
    assert resolved.profile.version == "2026-10-03/no-dll"
    assert resolved.source_status == SourceStatus.CURRENT_VERIFIED
    assert resolved.resolved_at == NOW


def test_incomplete_profile_is_rejected_by_default_and_explicitly_labeled_on_inspection():
    registry = canonical_profile_registry()
    arguments = (
        "lucid", "lucidpro_evaluation", AccountStage.EVALUATION,
        D("50000"), NOW,
    )
    with pytest.raises(ProfileSourceStatusError) as error:
        registry.resolve_profile(*arguments)
    assert error.value.actual == SourceStatus.INCOMPLETE
    inspected = registry.resolve_profile(*arguments, required_source_status=None)
    assert inspected.source_status == SourceStatus.INCOMPLETE
    assert inspected.profile.source_review.status == SourceStatus.INCOMPLETE


def test_source_conflict_cannot_be_resolved_as_current():
    registry = canonical_profile_registry()
    arguments = (
        "lucid", "lucidpro_funded_fixed_dll", AccountStage.FUNDED,
        D("25000"), NOW,
    )
    with pytest.raises(ProfileSourceStatusError) as error:
        registry.resolve_profile(*arguments)
    assert error.value.actual == SourceStatus.SOURCE_CONFLICT
    assert registry.profile_status(*arguments) == SourceStatus.SOURCE_CONFLICT


def test_expired_review_becomes_stale_and_is_never_returned_as_current():
    registry = canonical_profile_registry()
    after_due = TOPSTEP_REVIEWED_AT + timedelta(days=31)
    arguments = (
        "topstep", "trading_combine", AccountStage.EVALUATION,
        D("50000"), after_due,
    )
    with pytest.raises(ProfileSourceStatusError) as error:
        registry.resolve_profile(*arguments, version="2026-10-03/no-dll")
    assert error.value.actual == SourceStatus.STALE_REVIEW_REQUIRED
    inspected = registry.resolve_profile(
        *arguments, version="2026-10-03/no-dll", required_source_status=None,
    )
    assert inspected.source_status == SourceStatus.STALE_REVIEW_REQUIRED


def test_supported_profile_listing_filters_by_firm_and_actual_status():
    registry = canonical_profile_registry()
    current = registry.list_supported_profiles(
        NOW, firm_id="apex", source_status=SourceStatus.CURRENT_VERIFIED,
    )
    assert current
    assert all(item.firm_id == "apex" for item in current)
    assert all(item.source_status == SourceStatus.CURRENT_VERIFIED for item in current)
    lucid = registry.list_supported_profiles(NOW, firm_id="lucid")
    assert len(lucid) == 16
    assert all(item.source_status in {
        SourceStatus.INCOMPLETE, SourceStatus.SOURCE_CONFLICT,
    } for item in lucid)


def test_list_profile_versions_exposes_variants_without_collapsing_source_status():
    registry = canonical_profile_registry()
    versions = registry.list_profile_versions(
        "topstep", "trading_combine", AccountStage.EVALUATION,
        D("50000"), NOW,
    )
    assert [item.version for item in versions] == [
        "2026-10-03/dll", "2026-10-03/no-dll",
    ]
    assert all(item.source_status == SourceStatus.CURRENT_VERIFIED for item in versions)


def test_missing_profile_and_invalid_inputs_fail_explicitly():
    registry = canonical_profile_registry()
    with pytest.raises(ProfileNotFoundError):
        registry.resolve_profile(
            "unknown", "missing", AccountStage.EVALUATION, D("50000"), NOW,
        )
    with pytest.raises(ValueError):
        registry.list_supported_profiles(datetime(2026, 10, 4))
    with pytest.raises(ValueError):
        registry.resolve_profile(
            "topstep", "trading_combine", AccountStage.EVALUATION, 50000.0, NOW,
        )


def test_registry_rejects_duplicate_identity_and_overlapping_same_version():
    profile = trading_combine_profile(D("50000"))
    with pytest.raises(ValueError, match="duplicate profile identity"):
        PropFirmProfileRegistry((profile, profile))
    overlapping = replace(
        profile,
        effective_from=profile.effective_from + timedelta(days=1),
        source_review=replace(
            profile.source_review,
            reviewed_at=TOPSTEP_REVIEWED_AT,
            review_due_at=TOPSTEP_REVIEWED_AT + timedelta(days=30),
        ),
    )
    with pytest.raises(ValueError, match="overlapping profile effective windows"):
        PropFirmProfileRegistry((profile, overlapping))


def test_registry_treats_missing_source_review_as_incomplete():
    profile = replace(
        trading_combine_profile(D("50000")), source_review=None,
        effective_from=LUCID_REVIEWED_AT - timedelta(days=1),
    )
    registry = PropFirmProfileRegistry((profile,))
    with pytest.raises(ProfileSourceStatusError) as error:
        registry.resolve_profile(
            profile.firm_id, profile.program_id, profile.stage,
            profile.account_size, NOW, version=profile.version,
        )
    assert error.value.actual == SourceStatus.INCOMPLETE
