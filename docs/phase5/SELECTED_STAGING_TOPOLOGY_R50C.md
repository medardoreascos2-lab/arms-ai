# R50C Selected Phase 5 Staging Topology

## Selection

`SELECTED_TOPOLOGY=ISOLATED_LOCAL_PROCESS_STAGING`

Phase 5 will execute Candidate A from R50B: isolated local processes and
in-process replicas using loopback or injected transports, synthetic identities
and secrets, temporary directories, and the isolated Phase 3 SQLite store where
a real durable store is needed for local integration.

The PostgreSQL contract, SQL generation, migration plan, configuration, and
failure boundaries remain required. A real PostgreSQL rehearsal is classified
`BLOCKED_LOCAL_RUNTIME` while Docker, Podman, `psql`, `postgres`, and `pg_ctl`
are unavailable. SQLite evidence must never be relabeled as PostgreSQL evidence.

## Why this topology is selected

1. It is executable on the current host without downloading software,
   provisioning infrastructure, using paid services, or requesting credentials.
2. It preserves Phase 4 provider-neutral seams and can exercise application
   composition, authorization, tenant isolation, supervision, replicas,
   encryption format, backup/restore, load, failover ordering, packaging, and
   release gates.
3. It supports deterministic tests with fake clocks, injected failures, local
   receivers, synthetic tenants, and temporary state.
4. It introduces no broker endpoint, external delivery, production mutation,
   PAPER/LIVE position creation, or LIVE authority.
5. It keeps missing infrastructure visible instead of substituting simulated
   results for PostgreSQL, cloud IAM, secret management, telemetry, or off-host
   backup evidence.

## Process topology

| Role | Local Phase 5 form | State and authority |
| --- | --- | --- |
| API replicas | Two or more isolated application instances or composed clients | GET/read contracts plus authenticated synthetic ingest where explicitly tested; no trading endpoint or execution authority. |
| Durable application store | Temporary Phase 3 SQLite store | Local integration evidence only; exact financial serialization, migrations, audit, outbox, and restart behavior. |
| PostgreSQL candidate | Static Phase 4 PostgreSQL adapter and migration contracts | No connection attempted while runtime is unavailable; `BLOCKED_LOCAL_RUNTIME`. |
| Identity issuer | Local synthetic issuer with ephemeral test keys | Issues test claims only; validates issuer, audience, expiry, tenant, account, role, signature, and rotation. |
| Secret provider | In-memory or temporary test-only provider | Resolves references for scoped services; values never enter Git, manifests, logs, alerts, or reports. |
| Worker replicas | Multiple supervised local worker models | Durable leases, fencing, bounded retry, dead letter, graceful drain; injected local delivery only. |
| Scheduler replicas | Multiple fake-clock scheduler identities | One owner per job, safe takeover, stable idempotency; no external schedule service. |
| Metrics receiver | Bounded in-memory/local scrape representation | Provider-neutral metrics without external collector or public endpoint. |
| Alert receiver | Fake/local receiver | Sanitized events, dedupe, severity, recovery; no webhook, email, PagerDuty, Slack, or Telegram. |
| Backup service | Local encrypted archive contract in temporary directories | Ephemeral test key, integrity manifest, separate restore destination; no off-host upload. |
| Research engine | Existing Phase 3 research modules under resource governance | Synthetic/historical test inputs; promotion stops at human review. |
| Build and scan | Deterministic local package tooling | No registry push, image push, signing service, deployment, or production artifact promotion. |

## Network and trust boundaries

- Default transport is injected in-process communication or loopback.
- No arbitrary outbound network call is part of the selected topology.
- Broker, trading, payout, production, notification-provider, and cloud-control
  endpoints are prohibited.
- Every protected API source requires an authenticated principal before source
  invocation and enforces tenant/account permission scope.
- Service identities receive only the permissions required by their local role.
- Database, backup, worker, scheduler, and research failures do not weaken
  authorization or create execution side effects.

## Provider-neutral interfaces retained

Phase 5 continues to use explicit interfaces for:

- database targets, connections, transactions, migrations, and health;
- secret references and scoped providers;
- authenticated users, service identities, permissions, and replay checks;
- worker and scheduler leases, heartbeats, restart policies, and fencing;
- metrics, health components, alert policies, and alert receivers;
- backup manifests, encryption material references, restore validators, and
  disaster-recovery steps;
- build manifests, package verification, load measurements, and release gates.

Tests must depend on these interfaces and injected local implementations rather
than environment-specific global state.

## Future container mapping

| Local role | Container equivalent | Evidence that does not transfer automatically |
| --- | --- | --- |
| Local API instance | API container replica | Container user, filesystem, network policy, probes, signals, and resource limits. |
| SQLite integration store | PostgreSQL container and migration job | PostgreSQL transaction isolation, pool limits, concurrent server behavior, WAL, restart, and backup tooling. |
| Local worker model | Worker container replicas | Process signals, orchestration restart, distributed lease timing, and transport delivery. |
| Fake scheduler identities | Scheduler containers | Orchestrator failure timing and network partition behavior. |
| In-memory metrics/alerts | Collector and receiver containers | Scrape transport, retention, access controls, and alert delivery. |
| Temporary encrypted files | Backup job and isolated restore volume | Volume snapshots, database-consistent backup, key injection, and off-host durability. |

## Future cloud mapping

| Provider-neutral capability | Future managed capability | Required new evidence |
| --- | --- | --- |
| PostgreSQL adapter | Managed PostgreSQL | Approved version, private connectivity, TLS, IAM/credentials, pool sizing, failover, PITR, replica consistency, and restore. |
| Secret provider | Managed secret store | Workload identity, least privilege, rotation, revocation, access audit, and outage behavior. |
| Synthetic issuer | External OIDC provider | Tenant setup, issuer/audience, key discovery and rotation, revocation, user/service lifecycle, and audit. |
| Local metrics/alerts | Managed telemetry and paging | Retention, label controls, dashboards, SLOs, delivery, escalation, and incident ownership. |
| Encrypted local archive | Encrypted object backup | Key custody, immutability, retention, RPO/RTO, access policy, and timed restore. |
| Local package | Registry artifact | SBOM, scanning, signing/attestation, provenance, access policy, and promotion controls. |
| Local replicas | Orchestrated replicas | Multi-node/zone failure domains, autoscaling, network partitions, capacity, and rollback controller behavior. |

## Assumptions and invalid claims

- The host remains suitable for deterministic local Python tests and temporary
  files.
- Synthetic inputs are labeled and traceable to their fixtures.
- Local process success does not prove container, PostgreSQL, cloud, external
  identity, external secret, telemetry delivery, or production behavior.
- No Phase 5 result can be named `READY_FOR_PRODUCTION`.
- The strongest possible local release result is
  `READY_FOR_EXTERNAL_STAGING_PROVISIONING`; it authorizes planning and a later
  approval request, not provisioning or deployment.

## Selection status

`LOCAL_TOPOLOGY_SELECTED=TRUE`

`PAID_PROVISIONING_REQUIRED=FALSE`

`POSTGRESQL_RUNTIME_STATUS=BLOCKED_LOCAL_RUNTIME`

`PRODUCTION_DEPLOYMENT_AUTHORIZED=FALSE`

`LIVE_AUTHORITY=FALSE`
