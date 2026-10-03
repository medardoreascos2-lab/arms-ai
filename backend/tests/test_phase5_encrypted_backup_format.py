"""R56A tests for the encrypted local staging backup format."""

from datetime import datetime, timezone
import hashlib
import json

import pytest

from backend.phase5.encrypted_backup import (
    ENCRYPTED_STAGING_BACKUP_FORMAT,
    LOCAL_TEST_CIPHER_ALGORITHM,
    EphemeralStagingBackupKey,
    LocalEphemeralBackupCipher,
    StagingBackupCipher,
    StagingBackupEncryptionError,
    StagingBackupPayload,
    create_encrypted_staging_backup,
    open_encrypted_staging_backup,
)


NOW = datetime(2026, 10, 4, 5, 0, tzinfo=timezone.utc)
KEY_MATERIAL = bytes(range(32))
NONCE = bytes(reversed(range(32)))


def _payload():
    return StagingBackupPayload(
        database=b"SQLite format 3\x00tenant-a-row",
        database_schema_version=7,
        audit_continuity=b'{"tip":"audit-chain-tip-42"}',
        research_provenance=b'{"dataset":"research-dataset-17"}',
        created_at=NOW,
    )


def _cipher(material=KEY_MATERIAL):
    key = EphemeralStagingBackupKey(material, local_test_enabled=True)
    cipher = LocalEphemeralBackupCipher(
        key,
        local_test_enabled=True,
        nonce_factory=lambda size: NONCE,
    )
    return key, cipher


def test_encrypted_format_round_trip_contains_every_required_backup_domain():
    key, cipher = _cipher()
    payload = _payload()

    encrypted = create_encrypted_staging_backup(payload, cipher)
    restored = open_encrypted_staging_backup(encrypted, cipher)
    envelope = json.loads(encrypted)

    assert restored == payload
    assert restored.database == payload.database
    assert restored.database_schema_version == 7
    assert restored.audit_continuity == payload.audit_continuity
    assert restored.research_provenance == payload.research_provenance
    assert dict(restored.hash_manifest) == {
        "audit_continuity_sha256": hashlib.sha256(payload.audit_continuity).hexdigest(),
        "database_sha256": hashlib.sha256(payload.database).hexdigest(),
        "research_provenance_sha256": hashlib.sha256(payload.research_provenance).hexdigest(),
    }
    assert envelope["format"] == ENCRYPTED_STAGING_BACKUP_FORMAT
    assert envelope["algorithm"] == LOCAL_TEST_CIPHER_ALGORITHM
    assert envelope["key_id"] == key.key_id
    assert payload.payload_id not in encrypted.decode("ascii")


def test_envelope_hides_database_audit_and_research_plaintext():
    _, cipher = _cipher()
    encrypted = create_encrypted_staging_backup(_payload(), cipher)

    assert b"SQLite format 3" not in encrypted
    assert b"tenant-a-row" not in encrypted
    assert b"audit-chain-tip-42" not in encrypted
    assert b"research-dataset-17" not in encrypted


def test_ephemeral_key_and_cipher_are_explicitly_local_and_non_authorizing():
    key, cipher = _cipher()

    assert isinstance(cipher, StagingBackupCipher)
    assert str(key) == "[REDACTED]"
    assert repr(key) == "EphemeralStagingBackupKey([REDACTED])"
    assert key.local_test_only is True
    assert key.production_key_authorized is False
    assert cipher.local_test_only is True
    assert cipher.production_encryption_authorized is False
    assert cipher.external_storage_authorized is False
    assert cipher.execution_authorized is False
    assert cipher.production_mutation_authorized is False
    assert _payload().production_backup_authorized is False

    key.close()
    assert key.closed is True
    with pytest.raises(StagingBackupEncryptionError, match="closed"):
        cipher.encrypt(b"cannot-use-closed-key")


def test_local_test_enablement_and_nonce_reuse_fail_closed():
    with pytest.raises(StagingBackupEncryptionError, match="local-test"):
        EphemeralStagingBackupKey(KEY_MATERIAL)

    key = EphemeralStagingBackupKey(KEY_MATERIAL, local_test_enabled=True)
    with pytest.raises(StagingBackupEncryptionError, match="local-test"):
        LocalEphemeralBackupCipher(key)

    cipher = LocalEphemeralBackupCipher(
        key,
        local_test_enabled=True,
        nonce_factory=lambda size: NONCE,
    )
    cipher.encrypt(b"first")
    with pytest.raises(StagingBackupEncryptionError, match="reuse"):
        cipher.encrypt(b"second")
