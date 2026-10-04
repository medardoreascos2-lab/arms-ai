"""Fail-closed classification of approved MEDAR encryption providers."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.durable_memory_encryption import (
    DisabledDurableMemoryEncryption, EphemeralTestMemoryEncryption,
)


class EncryptionReadiness(str, Enum):
    DISABLED = "DISABLED"
    LOCAL_TEST_ONLY = "LOCAL_TEST_ONLY"
    PRODUCTION_UNAVAILABLE = "PRODUCTION_UNAVAILABLE"
    PRODUCTION_READY = "PRODUCTION_READY"


@dataclass(frozen=True)
class EncryptionReadinessResult:
    status: EncryptionReadiness
    production_sensitive_writes_allowed: bool = False
    local_synthetic_tests_allowed: bool = False

    def __post_init__(self) -> None:
        if self.production_sensitive_writes_allowed or self.status is EncryptionReadiness.PRODUCTION_READY:
            raise ValueError("no approved production MEDAR AEAD provider is installed")
        if self.local_synthetic_tests_allowed and self.status is not EncryptionReadiness.LOCAL_TEST_ONLY:
            raise ValueError("local-test permission requires test-only provider")


def assess_encryption_readiness(provider: object) -> EncryptionReadinessResult:
    # Exact approved types are required; caller-controlled flags cannot grant authority.
    if type(provider) is DisabledDurableMemoryEncryption:
        return EncryptionReadinessResult(EncryptionReadiness.DISABLED)
    if type(provider) is EphemeralTestMemoryEncryption:
        if provider.production_ready or not provider.local_test_only:
            return EncryptionReadinessResult(EncryptionReadiness.PRODUCTION_UNAVAILABLE)
        return EncryptionReadinessResult(EncryptionReadiness.LOCAL_TEST_ONLY, local_synthetic_tests_allowed=True)
    return EncryptionReadinessResult(EncryptionReadiness.PRODUCTION_UNAVAILABLE)
