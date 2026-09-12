# Legacy state inventory and migration dry-run (0.11A)

## Scope and invocation

This tool discovers and inspects persisted evidence. It does not migrate state,
start a runtime, repair files, select an account, or enable trading.

```powershell
python -B -m backend.legacy_state_inventory_cli --workspace C:/Development/ARMS-AI
python -B -m backend.legacy_state_inventory_cli --workspace C:/Development/ARMS-AI --state-path D:/archive/runtime-state-v2.json
```

JSON is printed to stdout. There is no output-file, apply, force, target-account,
backup, receipt-writing or cleanup option. Exit code 0 means an inventory was
produced, not that any candidate is migratable. Use -B (or
PYTHONDONTWRITEBYTECODE=1) to suppress Python interpreter bytecode caches as well.

## Discovery

All default sources are included even when absent:
- data/runtime/runtime-state-v2.json (historical ASGI)
- data/runtime_state_v2.json (historical CLI)
- data/risk_events.json
- backend/storage/trades.db
- data/reports/trade_journal.csv
- data/trade_plans.jsonl
- data/simulated_trades.jsonl
- backend/config/accounts.json, its temporary file and writer lock

ARMS_RUNTIME_STATE_PATH and repeated --state-path add candidates; they never
replace either historical default. Relative paths are resolved against the
absolute workspace root, not the caller's working directory. Drive-relative
Windows paths are rejected. The API default root comes from this module's
repository location. --catalog-path overrides only the catalog location.

Snapshot evidence, temporary files and writer locks are inventoried separately,
including missing sidecars. SQLite WAL/SHM/journal files are inventoried without
opening the database on disk. Scoped directory scanning discovers additional
runtime-state/runtime_state JSON files and orphan sidecars.

Catalog v2 account namespaces are discovery hints, not ownership evidence.
Both catalog and global legacy sources remain visible. Namespace hints outside
the workspace/configured snapshot-parent scopes are reported as discovery
errors; pass the source explicitly to expand the scope. The inventory never
uses a catalog as proof that legacy migration already happened.

Normalized aliases coalesce into one candidate. Physical duplicates use device
and file identity; identical-byte copies are reported separately using SHA-256.
Multiple candidates remain multiple candidates. Neither modification time,
generation, profile nor file order selects a winner.

## Historical formats

The runtime schema string remained 2.0 across these incompatible capabilities:

| Producer era | Available state |
| --- | --- |
| 2c4b82b | Lifecycle active positions, active protections/OCO, captured_at |
| 6808ed4 | Adds dated account state and open/closed portfolio |
| 8dac83f | Adds journal/history/PAPER records and durability v1 envelope |
| 181284f | Adds operation-bound evidence v1 sidecars for PENDING reconciliation |
| e67df3e | Strengthens semantic/economic validation and daily-adjustment evidence |
| 1f9f14d | Adds canonical account identity and per-account namespaces |

Durability v1 has generation and phase COMMITTED/PENDING, with SHA-256 over the
canonical payload excluding checksum. Evidence v1 additionally records operation
ID, pending checksum, generation, stage and recorded_at. Its checksum does not
prove account ownership or resolve PENDING.

SQLite journal, unversioned risk-event lists, plan/simulation JSONL and simulation
CSV are auxiliary formats. They are not complete runtime restore authorities.
Missing execution participants are never synthesized. Evidence envelopes retain
their own metadata while financial fields are inspected; a valid checksum does
not promote an observation to replay or migration authority.

## Classification and identity

The only classification values are SAFE_TO_MIGRATE, AMBIGUOUS, INCOMPLETE,
CORRUPT and UNSUPPORTED. Every result also carries eligible=false.

- CORRUPT: malformed encoding/JSON, duplicate keys, non-finite values, bad checksum,
  inconsistent declared identity or structural/economic contradictions.
- UNSUPPORTED: an unknown runtime/durability/evidence version or parsing size limit.
- INCOMPLETE: missing/unreadable source, changing source, missing required
  participants, unverified lock/database sidecar state.
- AMBIGUOUS: otherwise inspectable source without proven historical ownership.
  A fully coherent financial state is still AMBIGUOUS.
- SAFE_TO_MIGRATE: reserved. This phase has no historical attestation verifier,
  so there is deliberately no path that emits it.

Corruption/unsupported/incomplete diagnostics take precedence over ambiguity;
identity_evidence.proven remains false in every case. Missing identity alone
does not make a complete legacy snapshot structurally incomplete.

A canonical account_identity is reported as a claim. Even a correct ID, matching
PAPER ID, checksum and current catalog do not prove historical provenance of
these exact bytes. No user-supplied account name, path or arbitrary JSON
"proof" grants authority. Capital, limits, targets, risk percent, contracts,
profile, selector, generation and checksum are explicitly insufficient.
ARMS-PAPER-LIFECYCLE and ARMS-PAPER-001 are reusable identifiers.

Open positions, outstanding/unknown orders, protections, OCO and PENDING are
reported and are never eligible. Evidence is never replayed or reconciled.
potential_destination is null until ownership, destination and compatibility
can actually be demonstrated by a future approved mechanism.

## Report contract (version 1)

Top level: mode, workspace_root, migration_enabled=false, selected_source=null,
identity_attestation_supported=false, discovery_errors, runtime_candidates,
multiple_runtime_candidates, physical_duplicates, content_duplicates, candidates.

Each candidate includes:
- normalized_path, source_types, discovered_by, aliases, exists;
- size_bytes, sha256, detected format/schema, available timestamps;
- durability metadata and checksum presence/validity;
- identity claims, profile, PAPER account IDs and proof status;
- participants with presence/counts; financial summary;
- open_activity indicators and uncertainty;
- structural/semantic/economic validation results;
- classification, eligible, rejection_reasons, recommended_action;
- related artifacts and orphan status where applicable;
- potential_destination (null in 0.11A).

No source document or complete journal/database rows are echoed. Financial
summaries and identity claims are selected fields, not a dump of the source.
Reports have no audit-time timestamp or random IDs: unchanged inputs and options
produce the same logical report.

## Read-only validation and guarantees

The pure validator operates on parsed dictionaries. It checks required
participants, reference consistency, protections/OCO, account arithmetic,
risk blocks, financial field types, journal/history status and quantity links,
PAPER-only record modes and portfolio counts, then reuses validate_semantic_state for
PAPER execution linkage and economic/daily PnL. Instrument point values come
from the existing in-memory InstrumentProfileEngine, not guessed from capital.

These checks are diagnostics, not certification of a migration or replacement
for recovery validation against a proven destination runtime. No runtime,
broker, store, startup, restore, switch or checkpoint is constructed/called.

Source files are opened only in binary read mode, hashed using a single
descriptor and checked for identity/size/mtime changes during and after reading.
POSIX also compares ctime; Windows stat/fstat ctime semantics differ, so ctime
is excluded there. Parsing is bounded to 32 MiB; larger files are hashed and
reported UNSUPPORTED. Reads stop at the observed size plus one byte, rather than
following a continuously growing writer. Numeric overflow is reported as CORRUPT
for the affected candidate; an oversized CSV field is UNSUPPORTED. CSV syntax
errors are CORRUPT. These parsing failures do not abort the remaining inventory.

SQLite bytes are deserialized into an in-memory connection, then inspected
with query_only and temp_store=MEMORY. No SQLite connection is made to the
source path. Sidecars are not replayed. No filesystem locks are acquired.

This is an observation, not an atomic snapshot of a concurrently changing
installation. Observed instability blocks classification; an unchanged stat
signature is not an ownership proof or migration authorization. OS-managed
access-time changes are not controlled by the application.

Tests compare source bytes, hashes, sizes and mtimes before/after repeated runs,
deny write APIs and operational entry points, and verify no generation or
execution state is changed. Existing startup behavior is intentionally untouched:
this tool closes the discovery gap in the inventory, not in runtime admission.

## Future receipt contract (design only)

No receipt is written, accepted as proof, or used to suppress legacy discovery.
A future versioned receipt would need at least:

```json
{
  "receipt_version": 1,
  "source_hashes": [{"path": "<absolute source>", "sha256": "<exact bytes>"}],
  "source_paths": ["<source>", "<evidence and temporary sources>"],
  "destination_account_id": "<proven operative ID>",
  "destination_namespace": "<absolute namespace>",
  "adapter_version": "<explicit supported adapter>",
  "classification": "SAFE_TO_MIGRATE",
  "approval_plan_id": "<approval bound to immutable dry-run plan>",
  "state": "PREPARED",
  "identity_evidence_references": ["<independently verifiable provenance>"],
  "destination_hash": "<expected installed checkpoint>",
  "source_durable_generation": 1,
  "destination_durable_generation": 1
}
```

state would progress PREPARED -> COMMITTED only after installation and verification.
Source paths/hashes must cover every relevant artifact. Changed evidence, a
different destination, an occupied incompatible destination or an unproven ID
must block. Repeating a completed plan must not reinstall state or duplicate PnL.
Human approval cannot substitute for missing historical identity evidence.

Backup, installation, rollback, durable receipts and runtime startup integration
require a separate implementation phase.
