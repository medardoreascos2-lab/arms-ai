# R50A Phase 5 Staging Requirements Inventory

## Scope and safety boundary

Phase 5 validates an isolated staging architecture derived from Phase 4. It
does not authorize production deployment, external financial authority, broker
connectivity, order submission, PAPER or LIVE position creation, paid cloud
provisioning, or storage of real secrets.

The staging environment must use synthetic tenants, accounts, credentials,
market snapshots, evaluations, notifications, and research jobs. Every blocked,
invalid, stale, inconsistent, or unauthorized operation must fail closed and
produce no execution, portfolio, account, protection/OCO, or fill-like side
effect.

## Classification

- `REQUIRED`: must have deterministic Phase 5 evidence before the local staging
  release gate can pass.
- `OPTIONAL`: useful staging evidence that may be implemented when the local
  environment already supports it safely.
- `DEFERRED`: requires external provider selection, credentials, paid
  infrastructure, production authority, or a separate approval.

## Requirements matrix

| Area | Classification | Exact staging requirement | Acceptance evidence |
| --- | --- | --- | --- |
| Database contract | REQUIRED | Define a supported PostgreSQL version range, UTF-8 encoding, UTC session timezone, exact decimal serialization, bounded connections, forward-only migration ownership, transaction isolation, read-only behavior, tenant predicates, health checks, and backup semantics. | Versioned contract plus static adapter and migration tests. |
| PostgreSQL runtime | OPTIONAL | Use an ephemeral local PostgreSQL instance with synthetic credentials when Docker, Podman, or local PostgreSQL is already available. Never connect to an unapproved external database. | Migration and exact-decimal roundtrip evidence against the isolated instance. If unavailable, record `BLOCKED_LOCAL_RUNTIME` and continue with static contract tests. |
| Secrets | REQUIRED | Resolve provider-neutral secret references by environment and service identity; validate expiry and rotation metadata; never persist secret values; fail closed when a required reference is missing, expired, malformed, or out of scope. | Synthetic provider rehearsal and recursive leak/redaction tests. |
| External secret manager | DEFERRED | Select and configure a managed or organizational secret provider with workload identity, least privilege, rotation, revocation, and access audit. | Separate provider approval and staging credentials; no credentials are requested in Phase 5. |
| User and service identity | REQUIRED | Validate issuer, audience, signature, lifetime, tenant, account, role, service identity, key identity, and replay metadata before invoking a protected source. Deny unknown or incomplete claims. | Synthetic local OIDC/JWT issuer tests including key rotation and authorization side-effect assertions. |
| External identity provider | DEFERRED | Create an external staging tenant, applications, users, service principals, key rotation, revocation, and audit policy. | Separate account-access approval and provider-specific validation. |
| Workers | REQUIRED | Supervise local workers with start, heartbeat, bounded lease, crash detection, restart budget, retry quarantine, dead-letter inspection, generation identity, and graceful drain. External delivery remains disabled. | Deterministic fake-clock/process rehearsal and zero-effect failure tests. |
| Scheduler | REQUIRED | Run at least two synthetic scheduler identities with one current lease owner per job, fencing against stale owners, safe takeover, and stable idempotency keys. | Leader-death and takeover tests proving one-effect semantics. |
| Metrics | REQUIRED | Export provider-neutral local metrics for database, workers, scheduler, queues, latency, authorization denials, backups, research pressure, and migrations. Unknown required data must not report healthy. | Local metrics endpoint or sink contract with bounded labels and deterministic tests. |
| External telemetry | DEFERRED | Select an approved collector, retention, access control, dashboards, SLOs, and audit-safe log transport. | Provider-specific staging integration and operator approval. |
| Alerts | REQUIRED | Route database, worker, scheduler, backup, queue, disk, and authentication alerts to a fake/local receiver with dedupe, severity, sanitized evidence, and recovery transitions. | Local receiver rehearsal; no PagerDuty, Slack, Telegram, email, or webhook send. |
| Backup format | REQUIRED | Produce an encrypted, integrity-protected staging archive containing the isolated database, schema version, audit continuity, research provenance, and hash manifest. Keys are ephemeral test material and never committed. | Deterministic archive validation, wrong-key/corruption tests, and isolated restore evidence. |
| External backup storage | DEFERRED | Select encrypted off-host storage, key custody, immutability, retention, access control, RPO/RTO, and restore ownership. | Provider approval and timed external staging restore drill. |
| Build | REQUIRED | Reconstruct a deterministic staging package from a clean source tree and record Git SHA, dependency versions, schema/migration compatibility, feature flags, file modes, and artifact hashes. | Repeat-build hash comparison and package verification tests. |
| Artifact scanning | REQUIRED | Run locally available secret, unsafe-config, debug-mode, network-authority, LIVE/broker import, and world-writable-file checks. Fail closed on an unresolved critical finding. | Machine-readable local scan report tied to the build manifest. |
| External registry/signing | DEFERRED | Select artifact registry, signing or attestation policy, SBOM retention, vulnerability policy, and deployment identity. | Separate infrastructure approval; no image or artifact push in Phase 5. |
| Network boundaries | REQUIRED | Default to loopback or isolated in-process transports; allowlist service roles and destinations; prohibit broker endpoints and arbitrary outbound delivery; require authenticated internal calls. | Static configuration tests and composed-runtime assertions that no external send path is active. |
| Tenant isolation | REQUIRED | Enforce tenant and account scope at authentication, authorization, repository, cache, queue, metrics, backup, and restore boundaries under concurrent access. | Cross-tenant read/write denial tests and multi-replica isolation rehearsal. |
| API replicas | REQUIRED | Model at least two API instances sharing durable state. Preserve idempotency, replay rejection, consistent reads, and no duplicate writes. | Concurrent local replica tests with stable request and tenant identities. |
| Worker replicas | REQUIRED | Model multiple workers contending for durable leases with fencing and one-effect-safe retries. | Lease-expiry, crash, takeover, and duplicate-attempt tests. |
| Scheduler replicas | REQUIRED | Model multiple schedulers with a single leader per scheduled job and safe takeover. | Deterministic fake-clock leadership tests. |
| Load and backpressure | REQUIRED | Define small, medium, and stress synthetic profiles. Measure throughput, p50/p95/p99 latency, error rate, queue depth, saturation, and worker lag without claiming production equivalence. | Reproducible local load report and assertions for bounded resource use and operational reserve. |
| Failover | REQUIRED | Rehearse database unavailability, transaction abort, worker crash, scheduler takeover, key rotation, queue backlog, backup restore, and research overload in a documented recovery order. | Full synthetic failure drill with fail-closed state transitions and reconciliation evidence. |
| Application rollback | REQUIRED | Validate schema-compatible application rollback without reverse database migration, with worker drain, feature-flag containment, build identity, and explicit release gating. | Compatibility-matrix and rollback rehearsal tests. |
| Database restore escalation | REQUIRED | Restore only to a separate destination when application rollback is unsafe; verify checksum, schema, tenant isolation, audit, outbox, and research provenance before release. | Isolated restore escalation test; never overwrite the source environment. |
| Security review | REQUIRED | Audit token claims, tenant/account scope, replay, SQL parameterization, path traversal, unsafe deserialization, secret leakage, audit integrity, backup access, supply chain, and research abuse. | Phase 5 security tests and threat model with unresolved findings classified. |
| Release gate | REQUIRED | Produce only `READY_FOR_EXTERNAL_STAGING_PROVISIONING`, `HOLD`, or `BLOCKED`. Require all local Phase 5 suites, security, backup/restore, replicas, load/failover, artifact integrity, no LIVE authority, and unchanged published baselines. | Deterministic gate result and final integration report. `READY_FOR_PRODUCTION` is invalid. |
| Production and LIVE execution | DEFERRED | Production deployment and any broker, order, PAPER-position, or LIVE-position authority require independent authorization and safety validation outside Phase 5. | No Phase 5 artifact may satisfy or bypass this gate. |

## Local capability finding

At R50A, Docker, Podman, `psql`, `postgres`, and `pg_ctl` are unavailable on the
host. Phase 5 therefore selects no database runtime yet. R51B must record
`BLOCKED_LOCAL_RUNTIME` unless a safe, already-available local runtime is found;
it must not download, install, provision, or connect to an external service to
manufacture a passing result.

Python 3.14.6 and the repository's existing dependencies are available for
provider-neutral contracts, synthetic identities, isolated local files,
in-process replicas, fake clocks, deterministic load, static package checks,
and encrypted-format testing without adding a dependency unless later evidence
shows one is essential.

## Exit criteria for local Phase 5

The local roadmap is complete only when every `REQUIRED` row has traceable
tests or documentation, every unavailable `OPTIONAL` row is explicitly
classified, all `DEFERRED` items remain outside execution, the published V8 and
Phase 2-4 baselines are unchanged, and the release gate reports an allowed
state. A successful local result may permit planning external staging
provisioning; it cannot authorize production or LIVE trading.
