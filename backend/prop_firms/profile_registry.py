"""Immutable temporal registry for source-backed prop-firm profiles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .apex_profiles import standard_apex_profiles
from .lucid_profiles import standard_lucid_profiles
from .models_v1 import AccountStage, PropFirmProfile, SourceStatus
from .takeprofittrader_profiles import standard_takeprofittrader_profiles
from .topstep_profiles import standard_topstep_profiles


class ProfileRegistryError(ValueError):
    """Base error for deterministic registry resolution failures."""


class ProfileNotFoundError(ProfileRegistryError):
    """No profile matched the requested temporal identity."""


class AmbiguousProfileError(ProfileRegistryError):
    """More than one profile matched and the caller must specify a version."""


class ProfileSourceStatusError(ProfileRegistryError):
    """A profile exists but its source status is not accepted by the caller."""

    def __init__(self, actual: SourceStatus, required: SourceStatus) -> None:
        self.actual = actual
        self.required = required
        super().__init__(
            f"profile source status is {actual.value}; required {required.value}"
        )


@dataclass(frozen=True)
class ProfileDescriptor:
    firm_id: str
    program_id: str
    stage: AccountStage
    account_size: Decimal
    effective_from: datetime
    effective_to: datetime | None
    version: str
    source_status: SourceStatus
    config_hash: str


@dataclass(frozen=True)
class ResolvedProfile:
    profile: PropFirmProfile
    source_status: SourceStatus
    resolved_at: datetime


def _validate_at(at: datetime) -> None:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("at must be a timezone-aware datetime")


def _validate_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _validate_size(value: Decimal) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError("account_size must be a positive finite Decimal")


def _status(profile: PropFirmProfile, at: datetime) -> SourceStatus:
    if profile.source_review is None:
        return SourceStatus.INCOMPLETE
    return profile.source_review.status_at(at)


def _descriptor(profile: PropFirmProfile, at: datetime) -> ProfileDescriptor:
    return ProfileDescriptor(
        firm_id=profile.firm_id,
        program_id=profile.program_id,
        stage=profile.stage,
        account_size=profile.account_size,
        effective_from=profile.effective_from,
        effective_to=profile.effective_to,
        version=profile.version,
        source_status=_status(profile, at),
        config_hash=profile.config_hash,
    )


@dataclass(frozen=True)
class PropFirmProfileRegistry:
    profiles: tuple[PropFirmProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.profiles, tuple):
            raise ValueError("profiles must be an immutable tuple")
        if any(not isinstance(profile, PropFirmProfile) for profile in self.profiles):
            raise ValueError("registry contains an invalid profile")
        identities = [profile.identity for profile in self.profiles]
        if len(identities) != len(set(identities)):
            raise ValueError("registry contains a duplicate profile identity")

        groups: dict[tuple, list[PropFirmProfile]] = {}
        for profile in self.profiles:
            key = (
                profile.firm_id, profile.program_id, profile.stage,
                profile.account_size, profile.version,
            )
            groups.setdefault(key, []).append(profile)
        for versions in groups.values():
            ordered = sorted(versions, key=lambda profile: profile.effective_from)
            for previous, current in zip(ordered, ordered[1:]):
                if previous.effective_to is None or previous.effective_to > current.effective_from:
                    raise ValueError("registry contains overlapping profile effective windows")

    def resolve_profile(
        self,
        firm_id: str,
        program_id: str,
        stage: AccountStage,
        account_size: Decimal,
        at: datetime,
        *,
        version: str | None = None,
        required_source_status: SourceStatus | None = SourceStatus.CURRENT_VERIFIED,
    ) -> ResolvedProfile:
        """Resolve one active profile without hiding its source status.

        Passing ``required_source_status=None`` is an explicit opt-in to inspect
        unverified profiles. The returned wrapper still carries the actual status.
        """
        _validate_text(firm_id, "firm_id")
        _validate_text(program_id, "program_id")
        if not isinstance(stage, AccountStage):
            raise ValueError("stage must be an AccountStage")
        _validate_size(account_size)
        _validate_at(at)
        if version is not None:
            _validate_text(version, "version")
        if required_source_status is not None and not isinstance(
            required_source_status, SourceStatus
        ):
            raise ValueError("required_source_status must be a SourceStatus or None")

        matches = tuple(
            profile for profile in self.profiles
            if profile.firm_id == firm_id
            and profile.program_id == program_id
            and profile.stage == stage
            and profile.account_size == account_size
            and profile.effective_from <= at
            and (profile.effective_to is None or at < profile.effective_to)
            and (version is None or profile.version == version)
        )
        if not matches:
            raise ProfileNotFoundError("no active profile matches the requested identity")
        if len(matches) > 1:
            raise AmbiguousProfileError(
                "multiple profiles match; specify an exact profile version"
            )
        profile = matches[0]
        actual = _status(profile, at)
        if required_source_status is not None and actual != required_source_status:
            raise ProfileSourceStatusError(actual, required_source_status)
        return ResolvedProfile(profile, actual, at)

    def list_supported_profiles(
        self,
        at: datetime,
        *,
        firm_id: str | None = None,
        source_status: SourceStatus | None = None,
    ) -> tuple[ProfileDescriptor, ...]:
        _validate_at(at)
        if firm_id is not None:
            _validate_text(firm_id, "firm_id")
        if source_status is not None and not isinstance(source_status, SourceStatus):
            raise ValueError("source_status must be a SourceStatus or None")
        descriptors = (
            _descriptor(profile, at) for profile in self.profiles
            if profile.effective_from <= at
            and (profile.effective_to is None or at < profile.effective_to)
            and (firm_id is None or profile.firm_id == firm_id)
        )
        filtered = (
            item for item in descriptors
            if source_status is None or item.source_status == source_status
        )
        return tuple(sorted(
            filtered,
            key=lambda item: (
                item.firm_id, item.program_id, item.stage.value,
                item.account_size, item.version,
            ),
        ))

    def profile_status(
        self,
        firm_id: str,
        program_id: str,
        stage: AccountStage,
        account_size: Decimal,
        at: datetime,
        *,
        version: str | None = None,
    ) -> SourceStatus:
        return self.resolve_profile(
            firm_id, program_id, stage, account_size, at,
            version=version, required_source_status=None,
        ).source_status

    def list_profile_versions(
        self,
        firm_id: str,
        program_id: str,
        stage: AccountStage,
        account_size: Decimal,
        at: datetime,
    ) -> tuple[ProfileDescriptor, ...]:
        _validate_text(firm_id, "firm_id")
        _validate_text(program_id, "program_id")
        if not isinstance(stage, AccountStage):
            raise ValueError("stage must be an AccountStage")
        _validate_size(account_size)
        _validate_at(at)
        matches = (
            _descriptor(profile, at) for profile in self.profiles
            if profile.firm_id == firm_id
            and profile.program_id == program_id
            and profile.stage == stage
            and profile.account_size == account_size
        )
        return tuple(sorted(
            matches, key=lambda item: (item.effective_from, item.version, item.config_hash)
        ))


def canonical_profile_registry() -> PropFirmProfileRegistry:
    """Build the canonical read-only registry from all normalized firm profiles."""
    return PropFirmProfileRegistry(
        standard_topstep_profiles()
        + standard_apex_profiles()
        + standard_takeprofittrader_profiles()
        + standard_lucid_profiles()
    )
