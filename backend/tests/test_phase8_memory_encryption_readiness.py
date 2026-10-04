"""R108I production AEAD remains blocked without an approved implementation."""

import pytest

from backend.medar.durable_memory_encryption import (
    AESGCMEphemeralMemoryEncryption, DisabledDurableMemoryEncryption,
    EphemeralTestMemoryEncryption,
)
from backend.medar.memory_encryption_readiness import EncryptionReadiness, assess_encryption_readiness


def test_disabled_and_ephemeral_provider_cannot_claim_production_readiness():
    assert assess_encryption_readiness(DisabledDurableMemoryEncryption()).status is EncryptionReadiness.DISABLED
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        readiness = assess_encryption_readiness(provider)
        assert readiness.status is EncryptionReadiness.LOCAL_TEST_ONLY
        assert readiness.local_synthetic_tests_allowed
        assert not readiness.production_sensitive_writes_allowed


def test_aesgcm_provider_is_ready_only_for_sensitive_local_development():
    with AESGCMEphemeralMemoryEncryption(local_development_enabled=True) as provider:
        readiness = assess_encryption_readiness(provider)
        assert readiness.status is EncryptionReadiness.LOCAL_DEVELOPMENT_READY
        assert readiness.local_synthetic_tests_allowed
        assert readiness.sensitive_local_development_writes_allowed
        assert not readiness.production_sensitive_writes_allowed


def test_caller_controlled_production_flags_do_not_grant_encryption_authority():
    class ClaimedProductionProvider:
        production_ready = True
        local_test_only = False
    result = assess_encryption_readiness(ClaimedProductionProvider())
    assert result.status is EncryptionReadiness.PRODUCTION_UNAVAILABLE
    assert not result.production_sensitive_writes_allowed
    from backend.medar.memory_encryption_readiness import EncryptionReadinessResult
    with pytest.raises(ValueError):
        EncryptionReadinessResult(EncryptionReadiness.PRODUCTION_READY)
    with pytest.raises(ValueError):
        EncryptionReadinessResult(EncryptionReadiness.LOCAL_TEST_ONLY, production_sensitive_writes_allowed=True)
