# R51A PostgreSQL Staging Contract

## Scope and status

This contract defines the PostgreSQL database required for an ARMS AI staging
environment. It does not provision a database, resolve a secret, open a network
connection, or authorize an execution path.

`POSTGRESQL_RUNTIME_STATUS=BLOCKED_LOCAL_RUNTIME`

Docker, Podman, `psql`, `postgres`, and `pg_ctl` are unavailable on the current
host. R51A therefore records requirements and static acceptance criteria only.
SQLite remains valid local integration evidence, but it is not PostgreSQL
evidence and cannot satisfy the runtime checks in this document.

## Server baseline

| Item | Staging requirement | Failure behavior |
| --- | --- | --- |
| Engine | PostgreSQL Community or a compatible managed PostgreSQL service | Reject any different engine or compatibility layer until separately validated. |
| Version | Major version 16; the latest provider-approved 16.x security patch available at provisioning time | Refuse readiness when `server_version_num` is outside `160000..169999`. A major-version change requires a new compatibility and recovery rehearsal. |
| Encoding | Database and client encoding `UTF8` | Refuse migrations and readiness if either encoding differs. |
| Locale | Provider-supported deterministic locale selected once at creation; identifiers and authorization decisions must not depend on locale collation | Refuse a restore into a database whose locale differs from the backup manifest. |
| Timezone | Server, database role, migration role, and application sessions use `UTC` | Refuse readiness when `SHOW TIMEZONE` is not `UTC`. Persist application timestamps as canonical UTC text ending in `Z` until a reviewed migration changes the existing format. |
| Extensions | No PostgreSQL extension is required or permitted by the current schema | An extension request needs a reviewed contract change, privilege review, migration, backup/restore coverage, and approval before installation. |
| TLS | Required for any non-loopback or managed staging connection, with certificate and hostname verification | Refuse the connection if transport verification cannot be established. Local runtime absence does not waive this requirement. |

The application receives only an opaque connection reference. DSNs, passwords,
tokens, certificates, and provider credentials must come from the later secret
provider boundary and must never appear in configuration committed to Git,
health responses, logs, metrics, alerts, migration history, or test reports.

## Data representation

1. Existing durable documents remain immutable `BYTEA` payloads with a lowercase
   SHA-256 digest. A read must recompute and compare the digest before returning
   the document.
2. Financial decimals remain canonical, finite decimal text inside the durable
   payload. PostgreSQL binary floating types (`REAL` and `DOUBLE PRECISION`) are
   prohibited for money, price, quantity, PnL, risk, drawdown, or performance
   values.
3. If a future reviewed migration adds a queryable decimal column, it must use
   exact `NUMERIC` without an implicit rounding cast. The producer must reject
   a value that the chosen column cannot represent exactly. The migration must
   state its precision and scale and add boundary, overflow, round-trip, and
   restore tests before use.
4. All timestamps entering the existing schema are timezone-aware in the
   application and serialized as canonical UTC text with microseconds and a
   terminal `Z`. Naive, local-time, noncanonical, or server-default timestamps
   are rejected.
5. Application identifiers remain bounded validated text. Database-generated
   identifiers or timestamps must not replace the canonical application values.

## Schema and migration ownership

- The Phase 4 forward-only migration plan is the sole owner of the ARMS schema.
- The migration role is distinct from runtime roles. It may create or alter
  approved schema objects and update the migration metadata only while the
  migration job is running.
- Application API, worker, scheduler, backup, and read-only roles cannot execute
  DDL or modify migration metadata.
- Exactly one migration runner executes at a time. It must run with autocommit
  disabled and acquire the existing transaction-scoped PostgreSQL advisory lock
  before inspecting or changing schema state.
- Migration versions are contiguous from 1. Names are unique, statements are
  forward-only, and the stored migration history and chain checksum must match
  the application plan exactly.
- A migration, metadata update, and history update commit in one transaction.
  Any error rolls back the entire attempt. Destructive or data-copying SQL is
  outside the current automatic migration authority.
- A database newer than the application, missing metadata, incomplete history,
  checksum mismatch, or unexpected schema version is unavailable for service
  readiness. No downgrade, repair, fallback database, or partial startup occurs.

## Tenant and account isolation

1. Every tenant-owned primary key starts with `tenant_id`; every tenant-owned
   insert, conflict check, read, update, count, lease, and delete predicate must
   include the authenticated tenant identifier.
2. Application repositories are created for one validated tenant and reject a
   record carrying any other tenant before issuing SQL.
3. Account-scoped data must include both `tenant_id` and the authorized
   `account_id`. An account identifier alone is never an isolation boundary.
4. Runtime roles receive no cross-tenant administrative query capability.
   Migration and backup roles cannot be reused by the application.
5. Row-level security is not claimed by the current schema. Before external
   staging, either reviewed PostgreSQL RLS policies must add a second isolation
   layer or the release gate must explicitly record application-enforced
   isolation with adversarial multi-tenant runtime evidence. Missing evidence
   fails closed.
6. Connection pooling must reset transaction state, session settings, prepared
   statements, and any future tenant context before a connection is reused.

## Connection budget and session rules

The staging database is provisioned with at least `max_connections=40`. Five
connections are reserved for provider administration and recovery. ARMS may use
at most 35 connections across all replicas:

| Consumer | Maximum connections |
| --- | ---: |
| Two API replicas | 12 total (6 each) |
| Worker replicas | 8 total |
| Scheduler replicas | 2 total |
| Migration job | 1 |
| Backup and restore validation | 2 total |
| Read-only operations and diagnostics | 2 total |
| Failover and scaling reserve | 8 total |
| **ARMS total** | **35** |

- Each process has an explicit bounded pool; unbounded creation is prohibited.
- Pool acquisition, connection, statement, lock, and idle-transaction timeouts
  are finite configuration values. A timeout causes rollback and an unavailable
  or degraded component state; it never selects SQLite or another database.
- Runtime sessions set `application_name`, `timezone=UTC`, an explicit access
  mode, and least-privilege role. Read-only services use read-only transactions.
- A connection is not healthy until it proves server version, encoding,
  timezone, access mode, required schema version, and migration checksum.
- Capacity exhaustion refuses new work and surfaces a sanitized health code.
  It does not expand the pool automatically or bypass tenant/risk controls.

## Backup, restore, and recovery semantics

1. A successful backup represents one database-consistent point in time and
   records a manifest containing database identity, PostgreSQL major version,
   creation time in UTC, schema version, schema checksum, backup format version,
   content digest, encryption-key reference, and retention class. It contains
   no secret value.
2. A backup is successful only after the artifact and manifest are complete,
   encrypted by the approved staging backup provider, and integrity verified.
   A local plaintext export is never labeled as a staging backup.
3. Restore always targets a new isolated database. It never overwrites the
   source. The target must pass manifest integrity, decryption, version,
   migration-history, schema-checksum, tenant-isolation, exact-decimal, and
   record-count checks before it can be considered recovered.
4. Point-in-time recovery is not claimed until a provider supplies WAL/archive
   retention and a timed restore rehearsal proves the configured recovery point
   and recovery time objectives.
5. Backup retention, deletion protection, off-host durability, key rotation,
   and restore access are provider decisions deferred to approved external
   staging. Missing or stale backup evidence makes recovery readiness false.
6. A database outage, corrupt record, failed migration, failed backup, or failed
   restore cannot authorize trading, create a PAPER or LIVE position, mutate a
   portfolio, or produce a fill-like execution record.

## Required roles

| Role | Allowed capability | Explicitly prohibited |
| --- | --- | --- |
| Migration | Advisory lock and approved schema migration transaction | Runtime data access, execution authority, role administration |
| API read/write | Tenant-scoped approved tables and transactions | DDL, migration metadata mutation, cross-tenant access |
| Worker | Tenant-scoped outbox/lease operations required by reviewed workers | DDL, arbitrary application-table access, execution authority |
| Scheduler | Reviewed schedule/lease tables only | Portfolio or order mutation, DDL |
| Read-only | Tenant-scoped reads through approved repositories | Writes, DDL, migration execution |
| Backup | Provider backup operation and isolated restore target | Application runtime access, source overwrite, execution authority |

No database role has broker, order, PAPER, LIVE, portfolio, or account-execution
authority. Database availability is a data dependency and never an execution
authorization signal.

## External staging acceptance checks

R51B and R51C may use static or injected tests while the runtime is unavailable,
but only a future isolated PostgreSQL 16 environment can satisfy these checks:

1. Verify version, UTF8 client/database encoding, UTC sessions, TLS where
   applicable, no unapproved extensions, and the 40/35 connection budget.
2. Apply the schema from empty, reapply idempotently, reject altered history,
   reject a newer schema, and prove transaction rollback under injected failure.
3. Exercise concurrent migration runners and prove advisory-lock serialization.
4. Prove same-record idempotency and conflicting-payload rejection.
5. Prove cross-tenant and cross-account read/write denial across reused pooled
   connections and every replica/service role.
6. Prove exact decimal, timestamp, payload, and digest round trips at boundaries.
7. Exhaust the pool and inject connection loss, transaction abort, restart, and
   failover; verify no backend fallback and no committed partial write.
8. Create an encrypted consistent backup, restore it to an isolated target, and
   validate the manifest, schema, tenants, counts, digests, and recovery timing.
9. Confirm every rejected or unavailable path has zero broker calls, orders,
   positions, protections/OCO, portfolio/account mutation, fill-like records,
   and execution events.

## R51A decision

`POSTGRESQL_CONTRACT_DEFINED=TRUE`

`POSTGRESQL_RUNTIME_VALIDATED=FALSE`

`REAL_EXTERNAL_DATABASE_CREATED=FALSE`

`PRODUCTION_MUTATION_AUTHORIZED=FALSE`

`LIVE_AUTHORITY=FALSE`
