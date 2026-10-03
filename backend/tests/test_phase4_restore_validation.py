"""R44C tests for isolated backup restore validation."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from backend.phase4.local_backup import LocalBackupRunner, LocalBackupSources
from backend.phase4.restore_validation import (
    BackupRestoreValidator,
    RestoreDestinationMode,
    RestoreTableExpectation,
    RestoreValidationPlan,
)


NOW = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def linked_entries(count: int, *, research: bool = False):
    previous = None
    result = []
    for index in range(count):
        item = {
            "record_hash" if research else "event_hash": digest(f"item-{index}"),
            "previous_record_hash" if research else "previous_event_hash": previous,
        }
        if research:
            item["source_hash"] = digest(f"source-{index}")
        previous = item["record_hash" if research else "event_hash"]
        result.append(item)
    return result


def sources(root: Path, *, broken_audit=False, broken_research=False) -> LocalBackupSources:
    root.mkdir(parents=True)
    database = root / "phase4.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA user_version = 3")
        connection.execute("CREATE TABLE tenants (tenant_id TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE tenant_state ("
            "tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id), value TEXT NOT NULL)"
        )
        connection.executemany("INSERT INTO tenants VALUES (?)", (("tenant-a",), ("tenant-b",)))
        connection.executemany(
            "INSERT INTO tenant_state VALUES (?, ?)",
            (("tenant-a", "one"), ("tenant-b", "two"), ("tenant-a", "three")),
        )
    config = root / "config.json"
    profiles = root / "profiles.json"
    audit = root / "audit.json"
    research = root / "research.json"
    config.write_text('{"identities":[]}', encoding="utf-8")
    profiles.write_text('{"profiles":[]}', encoding="utf-8")
    audit_items = linked_entries(2)
    if broken_audit:
        audit_items[1]["previous_event_hash"] = digest("wrong")
    audit.write_text(json.dumps({"events": audit_items}), encoding="utf-8")
    research_items = linked_entries(2, research=True)
    if broken_research:
        research_items[1]["source_hash"] = "invalid"
    research.write_text(json.dumps({"records": research_items}), encoding="utf-8")
    return LocalBackupSources(database, config, audit, research, profiles)


def backup(tmp_path, **source_options):
    return LocalBackupRunner(
        tmp_path / "backups",
        retention_policy="LOCAL_7_DAYS",
        retention_period=timedelta(days=7),
        clock=lambda: NOW,
    ).run(sources(tmp_path / "source", **source_options), database_schema_version=3)


def plan(*, rows=3, tenants=("tenant-a", "tenant-b"), schema=3):
    return RestoreValidationPlan(
        schema,
        (
            RestoreTableExpectation("tenants", 2, "tenant_id", tenants),
            RestoreTableExpectation("tenant_state", rows, "tenant_id", tenants),
        ),
    )


def validator(tmp_path):
    return BackupRestoreValidator(
        tmp_path / "restores",
        mode=RestoreDestinationMode.ISOLATED_TEST,
    )


def test_restore_validates_checksums_schema_tenants_rows_audit_and_research(tmp_path):
    package = backup(tmp_path)
    report = validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    assert report.checksums_verified is True
    assert report.tenant_isolation_verified is True
    assert report.audit_continuity_verified is True
    assert report.research_provenance_verified is True
    assert report.audit_event_count == 2
    assert report.research_record_count == 2
    assert tuple(item.row_count for item in report.tables) == (2, 3)
    assert report.live_store_overwrite_authorized is False
    with sqlite3.connect(report.restore_directory / "database" / "snapshot.sqlite3") as restored:
        assert restored.execute("SELECT COUNT(*) FROM tenant_state").fetchone()[0] == 3


def test_tampered_backup_checksum_fails_before_restore_publication(tmp_path):
    package = backup(tmp_path)
    target = package.backup_directory / package.manifest.artifacts[1].relative_path
    target.write_bytes(target.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="size mismatch"):
        validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    assert list((tmp_path / "restores").iterdir()) == []


@pytest.mark.parametrize(
    ("validation_plan", "message"),
    (
        (plan(rows=4), "row count mismatch"),
        (plan(tenants=("tenant-a",)), "tenant isolation mismatch"),
        (plan(schema=4), "manifest schema version"),
    ),
)
def test_schema_row_count_and_tenant_mismatches_fail_closed(
    tmp_path, validation_plan, message
):
    package = backup(tmp_path)
    with pytest.raises(ValueError, match=message):
        validator(tmp_path).restore_and_validate(package.backup_directory, validation_plan)
    assert list((tmp_path / "restores").iterdir()) == []


def test_broken_audit_continuity_fails_and_cleans_staging(tmp_path):
    package = backup(tmp_path, broken_audit=True)
    with pytest.raises(ValueError, match="continuity"):
        validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    assert list((tmp_path / "restores").iterdir()) == []


def test_invalid_research_provenance_fails_and_cleans_staging(tmp_path):
    package = backup(tmp_path, broken_research=True)
    with pytest.raises(ValueError, match="source provenance"):
        validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    assert list((tmp_path / "restores").iterdir()) == []


def test_restore_never_overwrites_existing_validated_destination(tmp_path):
    package = backup(tmp_path)
    first = validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    database_hash = hashlib.sha256(
        (first.restore_directory / "database" / "snapshot.sqlite3").read_bytes()
    ).hexdigest()
    with pytest.raises(FileExistsError, match="already exists"):
        validator(tmp_path).restore_and_validate(package.backup_directory, plan())
    assert hashlib.sha256(
        (first.restore_directory / "database" / "snapshot.sqlite3").read_bytes()
    ).hexdigest() == database_hash
    assert not any(path.name.startswith(".restore-") for path in (tmp_path / "restores").iterdir())


def test_restore_plan_requires_tenant_isolation_and_safe_unique_tables():
    with pytest.raises(ValueError, match="tenant isolation"):
        RestoreValidationPlan(3, (RestoreTableExpectation("global_table", 1),))
    with pytest.raises(ValueError, match="safe SQL"):
        RestoreTableExpectation("table; DROP", 0)
    duplicate = RestoreTableExpectation("tenants", 2, "tenant_id", ("tenant-a",))
    with pytest.raises(ValueError, match="unique"):
        RestoreValidationPlan(3, (duplicate, duplicate))


def test_validator_has_only_isolated_test_mode_and_no_execution_authority(tmp_path):
    item = validator(tmp_path)
    assert tuple(RestoreDestinationMode) == (RestoreDestinationMode.ISOLATED_TEST,)
    assert item.live_store_overwrite_authorized is False
    assert item.production_mutation_authorized is False
    assert item.execution_authorized is False
