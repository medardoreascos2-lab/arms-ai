"""Isolated local database restore escalation after an incompatible app rollback."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from .app_rollback import AppRollbackStatus, StagingAppRollbackReport
from .encrypted_backup import (
    StagingBackupCipher,
    StagingRestorePolicy,
    open_encrypted_staging_backup,
)


_SHA256_LENGTH = 64
_MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


def _canonical(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_evidence_document(payload: bytes, label: str) -> dict[str, object]:
    if not isinstance(payload, bytes) or not payload or len(payload) > _MAX_EVIDENCE_BYTES:
        raise ValueError(f"{label} document is invalid")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        document: dict[str, object] = {}
        for key, value in pairs:
            if key in document:
                raise ValueError(f"{label} document contains duplicate fields")
            document[key] = value
        return document

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_float=lambda _: (_ for _ in ()).throw(
                ValueError(f"{label} document contains floating-point values")
            ),
            parse_constant=lambda _: (_ for _ in ()).throw(
                ValueError(f"{label} document contains non-finite values")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f"{label} document is invalid") from None
    if not isinstance(document, dict):
        raise ValueError(f"{label} document is invalid")
    return document


@dataclass(frozen=True)
class RestoreEscalationPlan:
    active_database: Path
    isolated_restore_root: Path
    isolated_destination: Path
    expected_tenants: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "active_database",
            "isolated_restore_root",
            "isolated_destination",
        ):
            path = getattr(self, name)
            if not isinstance(path, Path) or not path.is_absolute():
                raise ValueError(f"{name} must be an absolute Path")
        source = self.active_database.resolve(strict=False)
        root = self.isolated_restore_root.resolve(strict=True)
        destination = self.isolated_destination.resolve(strict=False)
        if self.isolated_restore_root.is_symlink() or not root.is_dir():
            raise ValueError("isolated restore root must be a non-symlink directory")
        try:
            destination.relative_to(root)
        except ValueError:
            raise ValueError("restore destination must remain inside isolated root") from None
        if destination == root or source == destination or source.parent == destination.parent:
            raise ValueError("restore destination must be isolated from active source")
        if (
            not isinstance(self.expected_tenants, tuple)
            or not self.expected_tenants
            or self.expected_tenants != tuple(sorted(set(self.expected_tenants)))
            or any(not isinstance(item, str) or not item for item in self.expected_tenants)
        ):
            raise ValueError("expected_tenants must be sorted unique nonempty text")


@dataclass(frozen=True)
class RestoreEscalationReport:
    destination: Path
    payload_id: str
    database_sha256: str
    database_schema_version: int
    tenants: tuple[str, ...]
    audit_tip: str
    research_evaluation_id: str
    backup_hash_verified: bool
    schema_verified: bool
    audit_chain_verified: bool
    tenant_isolation_verified: bool
    research_provenance_verified: bool
    active_source_unchanged: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    production_restore_authorized: bool = field(default=False, init=False)
    live_store_overwrite_authorized: bool = field(default=False, init=False)


class EncryptedRestoreEscalation:
    """Decrypts and validates a backup only in a new isolated local destination."""

    execution_authorized = False
    production_mutation_authorized = False
    production_restore_authorized = False
    live_store_overwrite_authorized = False

    def rehearse(
        self,
        rollback: StagingAppRollbackReport,
        encrypted_archive: bytes,
        cipher: StagingBackupCipher,
        policy: StagingRestorePolicy,
        plan: RestoreEscalationPlan,
    ) -> RestoreEscalationReport:
        if (
            not isinstance(rollback, StagingAppRollbackReport)
            or rollback.status is not AppRollbackStatus.BLOCKED_SCHEMA
            or not rollback.database_restore_escalation_required
            or rollback.application_rollback_completed
        ):
            raise ValueError("database restore requires a blocked schema rollback escalation")
        if not isinstance(plan, RestoreEscalationPlan):
            raise ValueError("plan must be RestoreEscalationPlan")
        if plan.active_database.is_symlink():
            raise ValueError("active source cannot be a symbolic link")
        source = plan.active_database.resolve(strict=True)
        if not source.is_file():
            raise ValueError("active source must be a regular file")
        if plan.isolated_restore_root.is_symlink():
            raise ValueError("isolated restore root cannot be a symbolic link")
        restore_root = plan.isolated_restore_root.resolve(strict=True)
        destination = plan.isolated_destination.resolve(strict=False)
        try:
            destination.relative_to(restore_root)
        except ValueError:
            raise ValueError("restore destination escaped isolated root") from None
        if destination.exists():
            raise FileExistsError("isolated restore destination already exists")
        if destination.parent.is_symlink():
            raise ValueError("isolated restore parent cannot be a symbolic link")

        source_hash_before = _sha256(source.read_bytes())
        payload = open_encrypted_staging_backup(
            encrypted_archive,
            cipher,
            restore_policy=policy,
        )
        manifest = dict(payload.hash_manifest)
        if manifest.get("database_sha256") != _sha256(payload.database):
            raise ValueError("backup database hash mismatch")

        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.parent / f".restore-{uuid4().hex}.sqlite3"
        destination_created = False
        try:
            with staging.open("xb") as handle:
                handle.write(payload.database)
                handle.flush()
            schema, tenants = self._validate_database(
                staging,
                policy.expected_database_schema_version,
                plan.expected_tenants,
            )
            audit_tip = self._validate_audit(
                payload.audit_continuity,
                plan.expected_tenants,
            )
            evaluation_id = self._validate_research(payload.research_provenance)
            if _sha256(source.read_bytes()) != source_hash_before:
                raise ValueError("active source changed during isolated restore")
            with staging.open("rb") as reader, destination.open("xb") as writer:
                destination_created = True
                shutil.copyfileobj(reader, writer)
                writer.flush()
            if _sha256(destination.read_bytes()) != manifest["database_sha256"]:
                raise ValueError("materialized restore hash mismatch")
            return RestoreEscalationReport(
                destination=destination,
                payload_id=payload.payload_id,
                database_sha256=manifest["database_sha256"],
                database_schema_version=schema,
                tenants=tenants,
                audit_tip=audit_tip,
                research_evaluation_id=evaluation_id,
                backup_hash_verified=True,
                schema_verified=True,
                audit_chain_verified=True,
                tenant_isolation_verified=True,
                research_provenance_verified=True,
                active_source_unchanged=True,
            )
        except Exception:
            if destination_created and destination.exists():
                destination.unlink()
            raise
        finally:
            if staging.exists():
                staging.unlink()

    @staticmethod
    def _validate_database(
        database: Path,
        expected_schema: int,
        expected_tenants: tuple[str, ...],
    ) -> tuple[int, tuple[str, ...]]:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("PRAGMA query_only = ON")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("restored database integrity check failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("restored database tenant isolation failed")
            schema = connection.execute("PRAGMA user_version").fetchone()[0]
            if schema != expected_schema:
                raise ValueError("restored database schema mismatch")
            tenants = tuple(
                row[0] for row in connection.execute(
                    "SELECT tenant_id FROM tenants ORDER BY tenant_id"
                ).fetchall()
            )
        if tenants != expected_tenants:
            raise ValueError("restored database tenant set mismatch")
        return schema, tenants

    @staticmethod
    def _validate_audit(payload: bytes, expected_tenants: tuple[str, ...]) -> str:
        document = _load_evidence_document(payload, "audit continuity")
        if not isinstance(document, dict) or set(document) != {"entries", "tip"}:
            raise ValueError("audit continuity document is invalid")
        entries = document["entries"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("audit continuity entries are invalid")
        previous = "0" * _SHA256_LENGTH
        seen_tenants: set[str] = set()
        allowed_tenants = set(expected_tenants)
        for sequence, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict) or set(entry) != {
                "event", "hash", "previous_hash", "sequence", "tenant_id"
            }:
                raise ValueError("audit continuity entry is invalid")
            tenant_id = entry["tenant_id"]
            if not isinstance(tenant_id, str) or tenant_id not in allowed_tenants:
                raise ValueError("audit continuity tenant scope is invalid")
            event = entry["event"]
            if not isinstance(event, str) or not event:
                raise ValueError("audit continuity event is invalid")
            seen_tenants.add(tenant_id)
            evidence = {
                "event": event,
                "previous_hash": entry["previous_hash"],
                "sequence": entry["sequence"],
                "tenant_id": tenant_id,
            }
            if entry["sequence"] != sequence or entry["previous_hash"] != previous:
                raise ValueError("audit continuity sequence is invalid")
            expected = _sha256(_canonical(evidence))
            if entry["hash"] != expected:
                raise ValueError("audit continuity hash is invalid")
            previous = expected
        if document["tip"] != previous:
            raise ValueError("audit continuity tip is invalid")
        if seen_tenants != allowed_tenants:
            raise ValueError("audit continuity tenant coverage is incomplete")
        return previous

    @staticmethod
    def _validate_research(payload: bytes) -> str:
        document = _load_evidence_document(payload, "research provenance")
        if not isinstance(document, dict) or set(document) != {
            "dataset_sha256", "evaluation_id", "strategy_sha256"
        }:
            raise ValueError("research provenance document is invalid")
        for name in ("dataset_sha256", "strategy_sha256"):
            value = document[name]
            if (
                not isinstance(value, str)
                or len(value) != _SHA256_LENGTH
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError("research provenance hash is invalid")
        evaluation_id = document["evaluation_id"]
        if not isinstance(evaluation_id, str) or not evaluation_id:
            raise ValueError("research provenance evaluation is invalid")
        return evaluation_id
