"""Read-only legacy discovery. Claims, checksums and selectors never prove ownership."""
from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from backend.services.legacy_snapshot_validation_v2 import (
    IncompleteSnapshot, at, validate_structure, validate_financial,
)

CLASSIFICATIONS = ("SAFE_TO_MIGRATE", "AMBIGUOUS", "INCOMPLETE", "CORRUPT", "UNSUPPORTED")
DEFAULT_SOURCES = {
    "data/runtime/runtime-state-v2.json": "runtime_snapshot",
    "data/runtime_state_v2.json": "runtime_snapshot",
    "data/risk_events.json": "risk_events",
    "backend/storage/trades.db": "journal_database",
    "data/reports/trade_journal.csv": "simulation_csv",
    "data/trade_plans.jsonl": "trade_plans",
    "data/simulated_trades.jsonl": "simulated_trades",
}
MAX_PARSE_BYTES = 32 * 1024 * 1024
ID_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]{0,127}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("non_finite_json_number")


def _json(data):
    value = json.loads(data, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    # Also catches overflowed finite-looking literals such as 1e400.
    json.dumps(value, allow_nan=False)
    return value


def _checksum(value):
    present = isinstance(value, dict) and "checksum" in value
    valid = None
    if present:
        payload = dict(value)
        expected = payload.pop("checksum")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        valid = isinstance(expected, str) and expected == hashlib.sha256(encoded).hexdigest()
    return {"present": present, "valid": valid}


def _text(value):
    return value if isinstance(value, str) and len(value) <= 256 else None


def _count(value):
    return len(value) if isinstance(value, (dict, list)) else None


def _signature(metadata):
    # Windows stat/fstat can expose different legacy ctime meanings. File identity,
    # size and mtime remain comparable; POSIX also benefits from change time.
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            None if os.name == "nt" else metadata.st_ctime_ns)


def _read(path):
    """One descriptor, streaming hash, bounded parsing, detect replacement/mutation."""
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("not_a_regular_file")
        digest = hashlib.sha256()
        chunks = []
        total = 0
        while chunk := stream.read(min(1024 * 1024, before.st_size + 1 - total)):
            digest.update(chunk)
            total += len(chunk)
            if total <= MAX_PARSE_BYTES:
                chunks.append(chunk)
        after = os.fstat(stream.fileno())
    stable = _signature(before) == _signature(after) == _signature(path.stat())
    return (b"".join(chunks) if total <= MAX_PARSE_BYTES else None,
            digest.hexdigest(), before, stable)


class LegacyStateInventoryV2:
    """No startup, broker, restore, checkpoint, write, lock acquisition or migration API."""

    def __init__(self, *, workspace_root=None, state_paths=(), environment=None, catalog_path="backend/config/accounts.json"):
        root = Path(workspace_root) if workspace_root is not None else Path(__file__).resolve().parents[2]
        if not root.is_absolute():
            raise ValueError("workspace_root must be absolute")
        self.root = root.resolve()
        self.state_paths = tuple(state_paths)
        self.environment = {"ARMS_RUNTIME_STATE_PATH":
                            (os.environ if environment is None else environment).get("ARMS_RUNTIME_STATE_PATH", "")}
        self.catalog_path = catalog_path

    def _path(self, value):
        path = Path(value).expanduser()
        # Drive-relative paths on Windows must not consult a drive's current directory.
        if path.drive and not path.is_absolute():
            raise ValueError("drive_relative_path_rejected")
        return (path if path.is_absolute() else self.root / path).resolve()

    def dry_run(self):
        specs = {}
        discovery_errors = []
        def add(value, kind, origin):
            try:
                path = self._path(value)
            except (ValueError, OSError, RuntimeError):
                discovery_errors.append({"source": str(value), "reason": "path_normalization_failed"})
                return None
            spec = specs.setdefault(path, {"source_types": set(), "discovered_by": set(), "aliases": set()})
            spec["source_types"].add(kind)
            spec["discovered_by"].add(origin)
            spec["aliases"].add(str(value))
            return path

        def snapshot(value, origin):
            path = add(value, "runtime_snapshot", origin)
            if path is not None:
                for suffix, kind in ((".evidence.json", "operation_evidence"), (".tmp", "temporary"),
                                     (".evidence.json.tmp", "temporary"), (".lock", "writer_lock")):
                    add(str(path) + suffix, kind, "snapshot_sidecar")
            return path

        for value, kind in DEFAULT_SOURCES.items():
            snapshot(value, "historical_default") if kind == "runtime_snapshot" else add(value, kind, "historical_default")
        configured = self.environment.get("ARMS_RUNTIME_STATE_PATH", "").strip()
        explicit = list(self.state_paths) + ([configured] if configured else [])
        scopes = {self.root / "data" / "runtime", self.root / "data"}
        for value in explicit:
            path = snapshot(value, "environment" if value == configured else "explicit_state_path")
            if path is not None:
                scopes.add(path.parent)
        catalog = add(self.catalog_path, "account_catalog", "catalog")
        if catalog is not None:
            add(str(catalog) + ".tmp", "temporary", "catalog_sidecar")
            add(str(catalog) + ".lock", "writer_lock", "catalog_sidecar")
        for suffix in ("-wal", "-shm", "-journal"):
            add("backend/storage/trades.db" + suffix, "database_sidecar", "database_sidecar")

        # Catalog contents are discovery hints, never identity attestations.
        catalog_bytes = None
        if catalog is not None and catalog.is_file():
            try:
                catalog_bytes, _, _, stable = _read(catalog)
                value = _json(catalog_bytes) if catalog_bytes is not None and stable else None
                if isinstance(value, dict) and value.get("version") == 2:
                    namespace = value.get("namespace_root")
                    accounts = value.get("accounts")
                    if not isinstance(namespace, str) or not isinstance(accounts, dict):
                        raise ValueError("invalid_catalog")
                    ns = self._path(namespace)
                    allowed = (self.root, *(self._path(p).parent for p in explicit))
                    if not any(ns.is_relative_to(parent) for parent in allowed):
                        raise ValueError("catalog_namespace_outside_discovery_scope")
                    scopes.add(ns)
                    for account_id in accounts:
                        if not isinstance(account_id, str) or not ID_PATTERN.fullmatch(account_id):
                            raise ValueError("invalid_catalog_identity")
                        snapshot(ns / account_id / "runtime-state.json", "catalog_hint")
            except (ValueError, OSError, TypeError, RecursionError):
                discovery_errors.append({"source": str(catalog), "reason": "catalog_discovery_incomplete"})

        for scope in sorted(scopes):
            if not scope.exists():
                continue
            def scan_error(error):
                discovery_errors.append({"source": str(scope), "reason": "directory_scan_failed"})
            # Unlike pathlib rglob on recent Python, onerror exposes unreadable
            # directories instead of silently presenting a complete inventory.
            for directory, dirs, filenames in os.walk(scope, onerror=scan_error, followlinks=False):
                dirs.sort()
                for name in sorted(filenames):
                    path = Path(directory) / name
                    if (name.startswith(("runtime-state", "runtime_state")) and ".json" in name
                            or name.endswith((".evidence.json", ".json.tmp", ".json.lock"))):
                        if name.endswith(".tmp"):
                            add(path, "temporary", "directory_scan")
                        elif name.endswith(".lock"):
                            add(path, "writer_lock", "directory_scan")
                        elif name.endswith(".evidence.json"):
                            add(path, "operation_evidence", "directory_scan")
                        elif name.endswith(".json"):
                            snapshot(path, "directory_scan")

        candidates = []
        signatures = {}
        for path, spec in sorted(specs.items()):
            candidate = self._inspect(path, spec)
            signatures[str(path)] = candidate.pop("_signature", None)
            candidates.append(candidate)
        by_path = {row["normalized_path"]: row for row in candidates}
        if catalog_bytes is not None and catalog is not None:
            row = by_path[str(catalog)]
            if row["sha256"] != hashlib.sha256(catalog_bytes).hexdigest():
                discovery_errors.append({"source": str(catalog), "reason": "catalog_changed_during_discovery"})

        for row in candidates:
            path = row["normalized_path"]
            related = [r["normalized_path"] for r in candidates if r["exists"] and (
                r["normalized_path"].startswith(path + ".")
                or ("journal_database" in row["source_types"] and r["normalized_path"] in {path + "-wal", path + "-shm", path + "-journal"}))]
            row["related_artifacts"] = related
            if "journal_database" in row["source_types"] and related:
                row["classification"] = "INCOMPLETE"
                row["rejection_reasons"].append("sqlite_sidecars_not_replayed")
            if "runtime_snapshot" in row["source_types"] and related:
                row["rejection_reasons"].append("sidecars_require_offline_review")
            if any(t in row["source_types"] for t in ("temporary", "operation_evidence")):
                base = path.removesuffix(".tmp").removesuffix(".evidence.json")
                row["orphaned"] = base not in by_path or not by_path[base]["exists"]
            expected = signatures[path]
            if expected is not None:
                try:
                    changed = _signature(Path(path).stat()) != expected
                except OSError:
                    changed = True
                if changed:
                    row["classification"] = "INCOMPLETE"
                    row["rejection_reasons"].append("source_changed_during_audit")

        physical, content = defaultdict(list), defaultdict(list)
        for row in candidates:
            signature = signatures[row["normalized_path"]]
            if signature and signature[1]:
                physical[signature[:2]].append(row["normalized_path"])
            if row["sha256"]:
                content[row["sha256"]].append(row["normalized_path"])
        runtime_candidates = [r["normalized_path"] for r in candidates if r["exists"] and "runtime_snapshot" in r["source_types"]]
        return {
            "report_version": 1, "mode": "READ_ONLY_DRY_RUN", "workspace_root": str(self.root),
            "migration_enabled": False, "selected_source": None,
            "identity_attestation_supported": False,
            "discovery_errors": discovery_errors, "runtime_candidates": runtime_candidates,
            "multiple_runtime_candidates": len(runtime_candidates) > 1,
            "physical_duplicates": sorted(v for v in physical.values() if len(v) > 1),
            "content_duplicates": sorted(v for v in content.values() if len(v) > 1),
            "candidates": candidates,
        }

    def _inspect(self, path, spec):
        result = {
            **{key: sorted(value) for key, value in spec.items()},
            "normalized_path": str(path), "exists": False, "size_bytes": None, "sha256": None,
            "format": None, "schema_version": None, "timestamps": {}, "durability": {},
            "checksum": {"present": False, "valid": None}, "participants": {},
            "identity_evidence": {"proven": False, "claimed": {}, "profile_name": None,
                                  "paper_account_ids": [], "reason": "no_historical_bytes_to_account_attestation"},
            "financial_summary": {}, "open_activity": {"present": None, "indicators": []},
            "validation_results": {"structural": "NOT_RUN", "semantic": "NOT_RUN", "economic": "NOT_RUN"},
            "classification": "AMBIGUOUS", "eligible": False, "potential_destination": None,
            "rejection_reasons": ["identity_not_proven"],
            "recommended_action": "PRESERVE_SOURCE_AND_OBTAIN_VERIFIABLE_IDENTITY_EVIDENCE",
        }
        try:
            metadata = path.stat()
            result["exists"] = True
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("not_a_regular_file")
            raw, digest, metadata, stable = _read(path)
            result.update(size_bytes=metadata.st_size, sha256=digest, _signature=_signature(metadata))
            result["timestamps"]["modified_at"] = datetime.fromtimestamp(metadata.st_mtime, timezone.utc).isoformat()
            if not stable:
                raise IncompleteSnapshot("source_changed_during_read")
            if raw is None:
                result["classification"] = "UNSUPPORTED"
                result["rejection_reasons"].append("parse_size_limit_exceeded")
                return result
            kinds = spec["source_types"]
            if "writer_lock" in kinds or "database_sidecar" in kinds:
                result.update(format="opaque_sidecar", classification="INCOMPLETE")
                result["rejection_reasons"].append("writer_or_database_state_unknown")
                return result
            if "journal_database" in kinds:
                # Deserialize bytes into memory: never open SQLite against the source.
                with closing(sqlite3.connect(":memory:")) as database:
                    database.deserialize(raw)
                    database.execute("PRAGMA temp_store=MEMORY")
                    database.execute("PRAGMA query_only=ON")
                    columns = [r[1] for r in database.execute("PRAGMA table_info(trades)")]
                    result["participants"] = {"journal_columns": columns}
                if not columns:
                    raise IncompleteSnapshot("missing_legacy_trades_table")
                result["format"] = "legacy_sqlite_journal"
                result["rejection_reasons"].append("auxiliary_source_not_runtime_state")
                return result
            if "simulation_csv" in kinds:
                rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig")), strict=True))
                result.update(format="simulation_csv", participants={"columns": rows[0] if rows else [], "rows": max(0, len(rows)-1)})
                result["rejection_reasons"].append("simulation_is_not_operational_evidence")
                return result
            if kinds & {"trade_plans", "simulated_trades"}:
                value = [_json(line) for line in raw.splitlines() if line.strip()]
            else:
                value = _json(raw.decode("utf-8-sig"))
            self._describe(result, value, kinds)
        except FileNotFoundError:
            result.update(classification="INCOMPLETE", recommended_action="NO_SOURCE_FOUND")
            result["rejection_reasons"].append("missing_source")
        except IncompleteSnapshot as exc:
            result["classification"] = "INCOMPLETE"
            result["rejection_reasons"].append(str(exc))
        except csv.Error as exc:
            result["classification"] = "UNSUPPORTED" if str(exc).startswith("field larger than field limit") else "CORRUPT"
            result["rejection_reasons"].append("csv_parser_rejected_source")
        except (OSError, PermissionError):
            result["classification"] = "INCOMPLETE"
            result["rejection_reasons"].append("source_not_readable")
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError, OverflowError, sqlite3.DatabaseError):
            result["classification"] = "CORRUPT"
            result["rejection_reasons"].append("invalid_source_encoding_structure_or_integrity")
        return result

    def _describe(self, result, value, kinds):
        result["checksum"] = _checksum(value)
        if isinstance(value, dict):
            result["schema_version"] = value.get("schema_version", value.get("version"))
            for key in ("captured_at", "recorded_at"):
                if _text(value.get(key)):
                    result["timestamps"][key] = value[key]
        if result["checksum"]["valid"] is False:
            result["classification"] = "CORRUPT"
            result["rejection_reasons"].append("checksum_mismatch")
        if "account_catalog" in kinds:
            if not isinstance(value, dict) or not isinstance(value.get("active_account"), str):
                raise ValueError("invalid_catalog")
            result["format"] = "account_catalog_v2" if value.get("version") == 2 else "legacy_profile_selector"
            result["participants"] = {"accounts": _count(value.get("accounts"))}
            result["identity_evidence"]["claimed"] = {"account_id": _text(value.get("active_account_id"))}
            result["identity_evidence"]["profile_name"] = _text(value.get("active_account"))
            result["rejection_reasons"].append("current_selector_is_not_historical_evidence")
            return
        if kinds & {"risk_events", "trade_plans", "simulated_trades"}:
            if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
                raise ValueError("invalid_auxiliary_records")
            result["format"] = "unversioned_record_list"
            result["participants"] = {"records": len(value)}
            result["timestamps"]["record_timestamps"] = sorted({_text(row.get("timestamp")) for row in value if _text(row.get("timestamp"))})
            result["rejection_reasons"].append("auxiliary_source_not_runtime_state")
            return
        evidence = "operation_evidence" in kinds
        result["format"] = "operation_evidence_v1" if evidence else "runtime_snapshot"
        state = value.get("state") if evidence and isinstance(value, dict) else value
        if not isinstance(state, dict):
            raise ValueError("invalid_snapshot_object")
        if evidence:
            result["durability"] = {key: value.get(key) for key in ("version", "generation", "stage", "operation_id", "pending_checksum")}
            result["rejection_reasons"].append("evidence_requires_exact_pending_link")
        else:
            durability = state.get("durability")
            result["durability"] = {key: durability.get(key) for key in ("version", "generation", "phase")} if isinstance(durability, dict) else {}
        identity = state.get("account_identity")
        if isinstance(identity, dict):
            result["identity_evidence"]["claimed"] = {key: (_text(identity.get(key)) if key != "runtime_generation" else
                identity.get(key) if type(identity.get(key)) is int else None) for key in ("account_id", "profile_name", "runtime_generation")}
        result["identity_evidence"]["profile_name"] = _text(at(state, "account_identity", "profile_name")) or _text(state.get("profile_name"))
        paper_id = _text(at(state, "execution_records", "paper", "account_id"))
        result["identity_evidence"]["paper_account_ids"] = [paper_id] if paper_id else []
        if paper_id in {"ARMS-PAPER-LIFECYCLE", "ARMS-PAPER-001"}:
            result["rejection_reasons"].append("reusable_paper_identifier")
        collections = {
            "lifecycle_positions": state.get("active_positions"),
            "portfolio_open": at(state, "account_portfolio", "open_positions"),
            "portfolio_closed": at(state, "account_portfolio", "closed_positions"),
            "journal": at(state, "execution_records", "journal"),
            "history": at(state, "execution_records", "history"),
            "orders": at(state, "execution_records", "paper", "orders"),
            "fills": at(state, "execution_records", "paper", "fills"),
            "paper_positions": at(state, "execution_records", "paper", "positions"),
            "protections": at(state, "protective_registry", "protections"),
            "oco": at(state, "oco_manager", "groups"),
        }
        result["participants"] = {key: {"present": value is not None, "count": _count(value)} for key, value in collections.items()}
        financial = at(state, "account_portfolio", "account", "state")
        if isinstance(financial, dict):
            result["financial_summary"] = {key: (financial.get(key) if isinstance(financial.get(key), (int, float, bool)) else None) for key in (
                "starting_balance", "balance", "equity", "realized_pnl", "daily_pnl",
                "unrealized_pnl", "drawdown", "profit_target", "trading_blocked")}
            result["timestamps"]["trading_day"] = _text(financial.get("trading_day"))
            for key in ("maximum_daily_loss", "maximum_total_drawdown"):
                limit = at(state, "account_portfolio", "account", key)
                result["financial_summary"][key] = limit if isinstance(limit, (int, float)) and not isinstance(limit, bool) else None
        indicators = [key for key in ("lifecycle_positions", "portfolio_open", "protections", "oco") if collections[key]]
        for key in ("orders", "paper_positions"):
            rows = collections[key]
            if isinstance(rows, dict) and any(not isinstance(row, dict) or row.get("status") not in {"FILLED", "CLOSED", "REJECTED", "CANCELLED"} for row in rows.values()):
                indicators.append(key)
        if state.get("pending_operation") or result["durability"].get("phase") == "PENDING":
            indicators.append("PENDING")
        if state.get("reconciliation") and at(state, "reconciliation", "resolved") is not True:
            indicators.append("unresolved_reconciliation")
        result["open_activity"] = {"present": bool(indicators), "indicators": indicators}
        if any(_count(value) is None for value in collections.values()):
            result["open_activity"]["unknown"] = True
        else:
            result["open_activity"]["unknown"] = False
        if indicators:
            result["rejection_reasons"].append("open_or_pending_activity_not_eligible")
        if "temporary" in kinds:
            result["rejection_reasons"].append("interrupted_write_not_authoritative")
        if state.get("schema_version") != "2.0":
            result["classification"] = "UNSUPPORTED"
            result["rejection_reasons"].append("unsupported_schema")
            return
        result["format"] += ":2.0:" + ("coordinated" if identity is not None else "records" if state.get("execution_records") is not None else "dated" if state.get("account_portfolio") is not None else "original")
        metadata = result["durability"]
        if evidence:
            if value.get("version") != 1:
                result["classification"] = "UNSUPPORTED"
                result["rejection_reasons"].append("unsupported_evidence_version")
                return
            if not result["checksum"]["present"]:
                raise IncompleteSnapshot("missing_evidence_checksum")
            if (type(value.get("generation")) is not int or value["generation"] < 1
                    or value.get("stage") not in {"PREPARED", "STARTED", "OBSERVED", "COMPLETED"}
                    or not _text(value.get("operation_id")) or not _text(value.get("pending_checksum"))):
                raise ValueError("invalid_evidence_metadata")
        if not evidence and ("durability" in state or "checksum" in state or state.get("execution_records") is not None):
            if not result["checksum"]["present"] or not metadata:
                raise IncompleteSnapshot("missing_durable_envelope")
            if metadata.get("version") != 1:
                result["classification"] = "UNSUPPORTED"
                result["rejection_reasons"].append("unsupported_durability_version")
                return
            if type(metadata.get("generation")) is not int or metadata["generation"] < 1 or metadata.get("phase") not in {"COMMITTED", "PENDING"}:
                raise ValueError("invalid_durability_metadata")
        if identity is not None:
            if (not isinstance(identity, dict) or set(identity) != {"account_id", "profile_name", "runtime_generation"}
                    or not isinstance(identity["account_id"], str) or not ID_PATTERN.fullmatch(identity["account_id"])
                    or not _text(identity["profile_name"]) or type(identity["runtime_generation"]) is not int or identity["runtime_generation"] < 1
                    or (paper_id is not None and paper_id != identity["account_id"])):
                raise ValueError("inconsistent_declared_account_identity")
        try:
            validate_structure(state)
            result["validation_results"]["structural"] = "PASS"
        except IncompleteSnapshot:
            result["validation_results"]["structural"] = "INCOMPLETE"
            raise
        except (ValueError, KeyError, TypeError):
            result["validation_results"]["structural"] = "FAIL"
            result["rejection_reasons"].append("structural_consistency_failed")
            raise
        try:
            validate_financial(state)
            result["validation_results"].update(semantic="PASS", economic="PASS")
        except (ValueError, KeyError, TypeError):
            result["validation_results"].update(semantic="FAIL", economic="FAIL")
            result["rejection_reasons"].append("semantic_or_economic_consistency_failed")
            raise
        # No evidence authority is implemented in 0.11A. Even a coherent canonical
        # claim cannot be promoted to SAFE_TO_MIGRATE by a path/catalog/checksum.
        result["rejection_reasons"].append("destination_not_proven")
