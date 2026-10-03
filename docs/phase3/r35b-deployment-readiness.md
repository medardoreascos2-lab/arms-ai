# R35B Phase 3 Deployment Readiness

## Decision

**HOLD — Phase 3 is not ready for production deployment.**

Assessment date: 2026-10-03

Reviewed branch: `phase3/durable-runtime-research`

Reviewed head: `f97186af3d53205a6def1c06e368d30b770b2606`

No deployment, external transport, broker connection, order submission, or LIVE
authorization was performed. The durable runtime and research engine remain
isolated from the frozen V8 application.

## Readiness matrix

| Area | Current evidence | Decision | Required production gate |
| --- | --- | --- | --- |
| Production database | `Phase3DurableStateStore` supplies isolated SQLite storage, WAL, foreign keys, integrity checks, exact serialized financial values, forward-only migrations, read-only open, and restart recovery. | HOLD | Select and approve an operational database; implement its repository and migration adapters; prove exact-decimal behavior, transaction isolation, concurrent writers, failover, pool exhaustion, restore, and replica consistency. SQLite is accepted only as the current local/single-host evidence store. |
| Secret store | Phase 3 contains no broker or provider credentials and its modules do not require secrets for local tests. | HOLD | Define runtime secret-manager injection, workload identities, least privilege, rotation/revocation, redaction, and fail-closed startup for database, API identity, telemetry, and backup credentials. Broker and LIVE credentials remain outside Phase 3. |
| Workers | `DurableOutbox` and `OutboxWorker` provide stable event identity, transactional leases, bounded retries, sanitized errors, dead-letter state, expired-lease recovery, and graceful claim shutdown. Delivery is injected and has no production transport. | HOLD | Package a supervised worker process; define safe transports, readiness, drain behavior, concurrency and tenant quotas; validate duplicate delivery across restarts and replicas; add dead-letter replay procedures and operational ownership. |
| Monitoring | The GET-only Phase 3 status projection requires runtime, ingestion, evaluation, outbox, worker, and research queue sources to succeed. Phase 2 structured telemetry remains bounded and in memory. | HOLD | Add an approved metrics/log exporter, retention and access controls, service and queue SLOs, alert thresholds, dropped-record accounting, dashboards, and incident runbooks. Probes must remain read-only. |
| Backups | Runtime recovery reconstructs incomplete deterministic Phase 3 operations from the durable store. This is transaction recovery, not backup or disaster recovery. | HOLD | Approve RPO/RTO; add encrypted backups, retention, integrity verification, point-in-time recovery where supported, isolated restore drills, post-restore reconciliation, and evidence that partial restore remains fail closed. |
| Tenant authentication and authorization | `ReadAuthorizationBoundary` enforces active principal, tenant match, role permission, entitlement, user scope, known account, and account scope. The composed runtime checks required reads before operational writes. | HOLD | Integrate canonical request authentication and principal construction; attach it to every mounted Phase 3 route; enforce tenant/account scope in repository queries; add expiry/revocation, rate and size limits, audit correlation, and end-to-end isolation tests. The standalone research and status routers are intentionally unmounted and do not yet perform transport authentication. |
| Deployment packaging | The root Dockerfile installs pinned direct packages and starts `backend.api.app:app`. It does not mount Phase 3 or start its migrations or worker. | HOLD | Produce separate reproducible API, migration, scheduler, and worker artifacts; run as non-root with a read-only filesystem; add startup/readiness/liveness probes, signed artifacts, SBOM and scanning, resource limits, graceful termination, rollback instructions, and environment validation. |
| Scaling and high availability | Durable worker leases and stable dedupe identities provide useful concurrency primitives. The current store is one SQLite file and no Phase 3 service topology or load evidence exists. | HOLD | Define tenancy and shard strategy, distributed locking assumptions, connection and queue capacity, horizontal worker limits, scheduler single-leader behavior, backpressure, load tests, failover tests, and multi-replica recovery. |

## Operational strengths already verified

- Exact financial serialization rejects binary floating-point state.
- Append-only snapshot, evaluation, audit, and outbox records preserve evidence.
- Migration and recovery inconsistencies fail closed.
- Authorization denials and rejected inputs create no snapshot, evaluation, or
  outbox execution effect.
- Outbox delivery is at least once with stable dedupe identity; no production
  transport is bundled.
- Research promotion ends at `READY_FOR_HUMAN_REVIEW` and grants no production
  mutation authority.
- Research, status, and dashboard contracts are read-only and detached from V8.

## Release gates

Production readiness requires automated evidence for all of the following:

1. Missing, stale, inconsistent, unauthorized, or partially restored state
   blocks the affected operation.
2. Denied or rejected requests produce no broker call, PAPER/LIVE position,
   protection order, portfolio mutation, source-account mutation, or fill-like
   journal record.
3. Every mounted route authenticates the caller and enforces tenant/account
   scope before reading or writing Phase 3 evidence.
4. Database migrations, backups, restores, workers, schedulers, monitoring, and
   failover work under the chosen production topology.
5. Readiness remains false when a required dependency, recovery check, migration,
   backup verification, or authorization service is unhealthy.
6. Human review remains mandatory for production candidate promotion.
7. LIVE execution requires a separate explicit authorization and independent
   safety validation outside this roadmap.

## Verification evidence

- Phase 3 integration suite: **657 passed** across 39 modules.
- Phase 2 changed tests plus Phase 3/research regression: **989 passed**.
- Broad research regression: **1329 passed**, with one inherited Phase 2 frozen
  hash declaration failure already recorded in R35A.
- Static execution-authority scan: no Phase 3 or research order-submission,
  broker-send, NinjaTrader entry, LIVE authorization, or automatic-promotion
  pattern found.
- Frozen V8 and Phase 2 baselines remained unchanged throughout Phase 3.

## Outcome

`DEPLOYMENT_READINESS=HOLD`

The implementation is suitable for continued isolated testing and a separately
approved production-infrastructure design. It is not an operational deployment
artifact and makes no LIVE capability claim.
