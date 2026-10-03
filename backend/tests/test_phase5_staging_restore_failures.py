"""R56C fail-closed tests for invalid encrypted staging restores."""

from datetime import datetime, timedelta, timezone
import json

import pytest

from backend.phase5.encrypted_backup import (
    EphemeralStagingBackupKey,
    LocalEphemeralBackupCipher,
    StagingBackupEncryptionError,
    StagingBackupPayload,
    StagingRestorePolicy,
    create_encrypted_staging_backup,
    open_encrypted_staging_backup,
)


CREATED = datetime(2026, 10, 4, 7, 0, tzinfo=timezone.utc)
KEY_MATERIAL = bytes(range(32))
WRONG_KEY_MATERIAL = bytes(range(1, 33))
NONCE = bytes(reversed(range(32)))


def _cipher(material=KEY_MATERIAL):
    key = EphemeralStagingBackupKey(material, local_test_enabled=True)
    return LocalEphemeralBackupCipher(
        key,
        local_test_enabled=True,
        nonce_factory=lambda size: NONCE,
    )


def _payload(*, schema_version=7, created_at=CREATED):
    return StagingBackupPayload(
        database=b"synthetic-sqlite-database",
        database_schema_version=schema_version,
        audit_continuity=b'{"tip":"synthetic-audit-tip"}',
        research_provenance=b'{"evaluation":"synthetic-r56c"}',
        created_at=created_at,
    )


def _policy(*, expected_schema=7, evaluated_at=CREATED + timedelta(hours=1)):
    return StagingRestorePolicy(
        expected_database_schema_version=expected_schema,
        maximum_backup_age=timedelta(days=1),
        evaluated_at=evaluated_at,
    )


def _canonical(document):
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_wrong_ephemeral_key_fails_before_restore_destination_is_created(tmp_path):
    encrypted = create_encrypted_staging_backup(_payload(), _cipher())
    restore_destination = tmp_path / "restore" / "staging.sqlite3"

    with pytest.raises(StagingBackupEncryptionError, match="authentication failed"):
        open_encrypted_staging_backup(
            encrypted,
            _cipher(WRONG_KEY_MATERIAL),
            restore_policy=_policy(),
        )

    assert restore_destination.exists() is False


def test_corrupt_archive_fails_authentication_without_partial_restore(tmp_path):
    encrypted = create_encrypted_staging_backup(_payload(), _cipher())
    document = json.loads(encrypted)
    first = document["ciphertext"][0]
    document["ciphertext"] = ("A" if first != "A" else "B") + document["ciphertext"][1:]
    corrupted = _canonical(document)
    restore_destination = tmp_path / "restore" / "staging.sqlite3"

    with pytest.raises(StagingBackupEncryptionError, match="authentication failed"):
        open_encrypted_staging_backup(corrupted, _cipher(), restore_policy=_policy())

    assert restore_destination.exists() is False


def test_partial_archive_fails_closed_without_partial_restore(tmp_path):
    encrypted = create_encrypted_staging_backup(_payload(), _cipher())
    partial = encrypted[: len(encrypted) // 2]
    restore_destination = tmp_path / "restore" / "staging.sqlite3"

    with pytest.raises(StagingBackupEncryptionError, match="invalid"):
        open_encrypted_staging_backup(partial, _cipher(), restore_policy=_policy())

    assert restore_destination.exists() is False


def test_schema_mismatch_fails_before_database_materialization(tmp_path):
    encrypted = create_encrypted_staging_backup(_payload(schema_version=6), _cipher())
    restore_destination = tmp_path / "restore" / "staging.sqlite3"

    with pytest.raises(StagingBackupEncryptionError, match="schema mismatch"):
        open_encrypted_staging_backup(encrypted, _cipher(), restore_policy=_policy())

    assert restore_destination.exists() is False


def test_stale_manifest_fails_before_database_materialization(tmp_path):
    stale_created = CREATED - timedelta(days=2)
    encrypted = create_encrypted_staging_backup(
        _payload(created_at=stale_created),
        _cipher(),
    )
    restore_destination = tmp_path / "restore" / "staging.sqlite3"

    with pytest.raises(StagingBackupEncryptionError, match="manifest is stale"):
        open_encrypted_staging_backup(encrypted, _cipher(), restore_policy=_policy())

    assert restore_destination.exists() is False


def test_restore_policy_has_no_execution_or_production_authority():
    policy = _policy()

    assert policy.execution_authorized is False
    assert policy.production_mutation_authorized is False
    assert policy.production_restore_authorized is False
