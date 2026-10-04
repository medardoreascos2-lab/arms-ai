"""R108H local-test encryption contract and fail-closed metadata tests."""

from dataclasses import replace

import pytest

from backend.medar.durable_memory_encryption import (
    DisabledDurableMemoryEncryption, EphemeralTestMemoryEncryption,
)


AAD = b"synthetic-memory-1|owner-a|tenant-a|TECHNICAL|INTERNAL|v1"


def test_disabled_provider_never_encrypts_or_decrypts():
    provider = DisabledDurableMemoryEncryption()
    assert not provider.production_ready
    with pytest.raises(PermissionError):
        provider.encrypt(b"synthetic text", associated_data=AAD)
    with pytest.raises(PermissionError):
        provider.decrypt(None, associated_data=AAD)


def test_local_test_provider_authenticates_content_and_context_without_production_claim():
    with pytest.raises(PermissionError):
        EphemeralTestMemoryEncryption()
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as provider:
        payload = provider.encrypt(b"synthetic test memory", associated_data=AAD)
        assert payload.ciphertext != b"synthetic test memory"
        assert b"synthetic test memory" not in payload.ciphertext
        assert "synthetic test memory" not in repr(payload)
        assert payload.authenticated and payload.local_test_only
        assert not provider.production_ready
        assert provider.decrypt(payload, associated_data=AAD) == b"synthetic test memory"
        with pytest.raises(PermissionError):
            provider.decrypt(payload, associated_data=AAD + b"|wrong")
        with pytest.raises(PermissionError):
            provider.decrypt(replace(payload, key_version="wrong"), associated_data=AAD)
        with pytest.raises(PermissionError):
            provider.decrypt(replace(payload, nonce_metadata="wrong"), associated_data=AAD)
        with pytest.raises(PermissionError):
            provider.decrypt(replace(payload, ciphertext=payload.ciphertext[:-1]), associated_data=AAD)
        tampered = payload.ciphertext.replace(b"ciphertext", b"ciphertexu", 1)
        with pytest.raises(PermissionError):
            provider.decrypt(replace(payload, ciphertext=tampered), associated_data=AAD)
    with pytest.raises(PermissionError):
        provider.decrypt(payload, associated_data=AAD)


def test_other_ephemeral_key_cannot_decrypt_payload():
    with EphemeralTestMemoryEncryption(local_test_enabled=True) as first, EphemeralTestMemoryEncryption(local_test_enabled=True) as second:
        payload = first.encrypt(b"synthetic test memory", associated_data=AAD)
        with pytest.raises(PermissionError):
            second.decrypt(payload, associated_data=AAD)
