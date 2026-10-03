# ARMS AI Phase 2 deployment readiness — R29B

**Assessment date:** 2026-10-03

**Branch:** `phase2/prop-firm-engine`

**Assessed code:** `ed7bdbb9ab11c2e71e72ded538fefd148575f176`

**Decision:** **HOLD — Phase 2 is not deployable as an operational service**

No deployment was performed. This report inventories the runtime, API, database, worker, secret, monitoring, backup, and packaging work required before a separate deployment authorization can be considered.

## 1. Scope and safety boundary

Phase 2 currently provides isolated, tested domain foundations for:

- source-backed prop-firm profiles and version selection;
- immutable account snapshots;
- fail-closed account, payout, and multi-account policy evaluation;
- aggregate portfolio and identified trade-journal analytics;
- an isolated policy API router;
- notification events, dispatch policy, and a test-only Telegram adapter;
- user entitlements and membership policy;
- structured Phase 2 telemetry records and a bounded in-memory sink.

These components do not authorize orders, create PAPER or LIVE positions, mutate broker state, or grant canonical administration. Policy eligibility is advisory compliance output only. Source records marked `INCOMPLETE`, `SOURCE_CONFLICT`, stale, missing, or otherwise unacceptable remain fail closed.

## 2. Readiness summary

| Area | Current evidence | Readiness | Required release gate |
|---|---|---:|---|
| Runtime | Pure Python domain modules and deterministic adapters exist. There is no Phase 2 composition root, startup recovery, or account-state ingestion service. | HOLD | Build and test an explicit Phase 2 application factory with fail-closed dependency validation and recovery. |
| API | The `/api/v1/prop-firms` router is tested in isolation and intentionally absent from `backend.api.app`. | HOLD | Add authentication, tenant/account authorization, entitlement checks, bounded request controls, audit correlation, and an explicitly approved mount point. |
| Database | Phase 2 has immutable models and read adapter protocols, but no durable schema, repository, migrations, or transactional state boundary. | HOLD | Define and test durable schemas, migrations, exact decimal storage, concurrency rules, and restart reconstruction. |
| Workers | Evaluation and test dispatch are process-local. There is no Phase 2 worker, durable queue, outbox, lease, or dead-letter handling. | HOLD | Implement durable notification/outbox processing only after its delivery and recovery contract is approved. |
| Secrets | Phase 2 contains no live provider credentials or broker credentials. Telegram is restricted to `DISABLED` and `TEST`. | HOLD | Define secret-manager injection, rotation, least privilege, redaction, and startup failure behavior. |
| Monitoring | Structured `arms.phase2.*` records exist with sensitive-data rejection. The only sink is bounded and in memory. | HOLD | Add an approved exporter, retention, dashboards, alerts, sink-health checks, and cardinality budgets without recording personal or account identifiers. |
| Backup | No Phase 2 backup, restore, retention, or recovery-point contract exists. | HOLD | Approve RPO/RTO, encrypted backup scope, restore validation, and disaster-recovery drills. |
| Packaging | The repository Dockerfile starts `backend.api.app`, which does not mount the Phase 2 router. It has no Phase 2 migrations, worker image, health check, or deployment manifest. | HOLD | Produce reproducible API/worker artifacts, non-root hardening, health/readiness probes, migration gates, SBOM/scanning, and rollback instructions. |

## 3. Runtime inventory

### Available

- Python 3.14 is the current container and test runtime.
- Domain values use immutable dataclasses, timezone-aware timestamps, strict booleans and integers, and `Decimal` for financial values.
- The canonical profile registry resolves profiles by firm, program, stage, account size, effective time, and optional version.
- Multi-account evaluation returns immutable results and does not mutate accounts.
- Known source gaps are represented through profile source status and fail-closed outcomes.

### Missing

- A Phase 2 application factory and configuration schema.
- A trusted source for account snapshots and a freshness contract tied to ingestion time.
- Startup dependency checks for persistence, clocks, profile catalog integrity, and required adapters.
- Restart recovery that reconstructs membership, account snapshot, notification, and audit state.
- Runtime ownership rules for profile refresh, snapshot capture, and evaluation scheduling.
- Graceful shutdown and in-flight work reconciliation for Phase 2 services.

### Runtime gate

Startup must fail closed when a required repository, source catalog, clock, account snapshot provider, authorization dependency, or recovery check is unavailable or inconsistent. A failed startup must not expose an evaluation endpoint as healthy.

## 4. API inventory

### Available

The isolated router defines:

- `GET /api/v1/prop-firms/profiles`
- `GET /api/v1/prop-firms/profiles/resolve`
- `POST /api/v1/prop-firms/evaluate/account`
- `POST /api/v1/prop-firms/evaluate/accounts`

The POST operations calculate policy results only. They do not execute trades or mutate account state. Transport models reject extra fields and floating-point financial input.

### Missing

- Mounting in an approved application.
- Canonical request authentication.
- Tenant and account ownership checks.
- Entitlement and membership enforcement.
- Rate limits, body-size limits, batch-size limits, and request timeouts.
- Stable error-envelope and API-version compatibility policy.
- Audit records that correlate a request with the selected profile and snapshot digest without exposing sensitive identifiers.
- OpenAPI review and consumer contract tests for an operational deployment.

### API gate

The router must remain unmounted until the full authorization chain is injected and tested. `allow_unverified=true` must be unavailable to ordinary users; any future diagnostic access requires canonical admin authorization and must remain non-executable. API reads and evaluations must preserve zero trading side effects.

## 5. Database and state inventory

### Durable entities required

- versioned profile source reviews and activation history;
- immutable account snapshot envelopes and digests;
- evaluation request/result audit records;
- linked-account ownership and tenant scope;
- membership records and effective plan versions;
- notification outbox, delivery attempts, dedupe keys, and terminal status;
- telemetry export checkpoints where required;
- trade-journal identity links used by Phase 2 analytics.

### Data rules

- Financial values require exact decimal columns with explicit scale; binary floating point is unacceptable.
- Timestamps require UTC storage plus explicit source/session semantics.
- Snapshot and evaluation records must be append-only or otherwise fully auditable.
- Profile identity requires firm, program, stage, account size, version, and effective time.
- Tenant and account relationships require database-enforced uniqueness and referential integrity.
- All writes that publish an evaluation and related audit/outbox records require a defined atomic transaction boundary.

### Existing storage limitation

The repository's existing `backend/storage/journal_database.py` is a legacy SQLite journal with `REAL` financial columns. It is not a Phase 2 persistence implementation and must not be silently reused for exact policy, payout, membership, or recovery state.

### Database gate

Choose and approve the operational database, add forward and rollback migrations, test concurrent updates, and prove clean restart reconstruction. Missing or partially migrated state must block the affected operation.

## 6. Worker inventory

### Current state

- Policy evaluation is synchronous and pure.
- Notification dispatch has deterministic retry policy, local dedupe, local rate limiting, and fake providers.
- Telegram has no live mode, token, endpoint, SDK, or network transport.
- No Phase 2 background worker is started by the current application.

### Required before external notification delivery

- A transactional outbox written with the source event.
- Durable idempotency and dedupe across restarts and replicas.
- Leased work claims with expiration and safe recovery.
- Bounded retry with persisted next-attempt time.
- Dead-letter state and an operator replay process that cannot duplicate delivery silently.
- Per-provider and per-tenant quotas.
- Graceful drain and restart tests.
- Delivery receipts that never imply a trade fill or execution authorization.

No worker is required merely to expose synchronous read-only evaluation, but the API cannot be released until its other gates are satisfied.

## 7. Secret inventory

Phase 2 currently needs no secret for its pure domain tests. An operational service would require only secrets for explicitly approved infrastructure, such as:

- database credentials;
- canonical API authentication and signing material;
- notification-provider credentials after a separate live-provider review;
- telemetry exporter credentials;
- backup encryption and object-store credentials.

Requirements:

- inject secrets from an approved secret manager at runtime;
- never place secrets in source, image layers, command arguments, telemetry, events, or exception details;
- rotate credentials and document revocation;
- scope service identities by API, worker, migration, monitoring, and backup duties;
- fail startup when a required secret is missing or malformed;
- keep broker and LIVE trading credentials outside Phase 2 because this phase has no execution authority.

## 8. Monitoring inventory

### Available

`backend.observability` produces structured metrics/events for rule evaluation, profile freshness, API calls, notifications, and account analytics. Names are restricted to `arms.phase2.*`; values and dimensions are bounded; sensitive keys and recognizable credential text are rejected.

### Missing

- exporter and collection protocol;
- retention and access policy;
- dashboards and alert thresholds;
- sink availability and dropped-record accounting;
- service health, queue depth, retry age, database pool, migration, and backup metrics;
- deployment/version labels with bounded cardinality;
- runbooks linked from alerts.

### Minimum alerts

- profile source stale, incomplete, or conflicting;
- account snapshot missing or stale;
- rule evaluation blocked because required data is unavailable;
- authorization or entitlement dependency unavailable;
- notification outbox age, retry exhaustion, or dead-letter growth;
- telemetry sink unavailable;
- database migration mismatch or recovery failure;
- backup failure or overdue restore verification.

Health and status probes must be read-only and must never submit or prepare an order.

## 9. Backup and recovery inventory

### Backup scope

- operational database and migration metadata;
- profile source evidence and approved profile versions;
- immutable snapshots and evaluation audit history;
- memberships and tenant/account links;
- notification outbox, attempts, dedupe, and dead-letter state;
- journal identity data required for reproducible analytics;
- configuration versions, excluding raw secret values.

### Required controls

- approved RPO and RTO;
- encrypted backups with independent access control;
- retention and deletion schedules;
- checksum and completeness verification;
- point-in-time recovery where the selected database supports it;
- scheduled restore drills into an isolated environment;
- reconciliation checks after restore;
- evidence that an incomplete restore leaves affected capabilities blocked.

## 10. Deployment packaging inventory

### Current image

The root Dockerfile installs pinned Python packages, copies `backend` and `docs`, exposes port 8000, and starts `backend.api.app:app`. That entry point is the existing application and does not register the Phase 2 policy router. The image therefore is not a Phase 2 deployment artifact.

### Required artifacts

- explicit Phase 2 API application entry point;
- separate worker entry point if live notifications are later approved;
- migration job with one-shot credentials;
- reproducible lock or hash-verified dependency input;
- non-root runtime user and read-only filesystem strategy;
- liveness, readiness, and startup probes;
- resource limits and graceful termination settings;
- environment-specific configuration validation;
- image signing, SBOM, dependency scanning, and provenance;
- deployment and rollback manifests;
- smoke tests that verify read-only behavior and zero execution side effects.

## 11. Safety acceptance gates

Deployment authorization requires automated evidence that:

1. `accepted=false` produces no broker call, PAPER position, LIVE position, protection order, account mutation, portfolio mutation, journal fill, or execution event.
2. Missing, stale, inconsistent, incomplete, conflicting, or unauthorized inputs fail closed.
3. Policy eligibility never becomes trade authorization.
4. API reads, evaluations, dashboards, health checks, telemetry, and notification subscriptions cannot trade.
5. Entitlements and memberships cannot replace authentication or canonical admin authorization.
6. Telegram and other providers remain disabled until separately reviewed credentials, transport, audit, and recovery controls exist.
7. Recovery reconstructs actual operational state before readiness is reported.
8. PAPER and LIVE remain explicitly separated; Phase 2 has no LIVE execution path.

## 12. Verification evidence used for this assessment

- R29A focused tests: **16 passed**.
- Phase 2 cumulative regression through R29A: **373 passed**.
- External warning: one Starlette `TestClient` deprecation warning; no Phase 2 test failure.
- Frozen V8 manifest revalidation after R29A: **PASS**.
- Phase 2 router search confirms it is imported only by its module and tests, not by `backend.api.app` or `backend.api.asgi`.
- Static inspection confirms the Telegram adapter has no live transport and the observability package has no network exporter.

## 13. Release decision and next action

**Release decision: HOLD.** Domain foundations are suitable for continued integration review, but runtime composition, authorization, durable state, recovery, external delivery, monitoring export, backup, and production packaging are absent.

The next authorized milestone is R30A: run the cross-component Phase 2 integration review, execute the relevant suites, fix only verified Phase 2 defects, and publish the final integration report. R30A does not authorize deployment or LIVE trading.
