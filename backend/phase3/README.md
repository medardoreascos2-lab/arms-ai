# Phase 3 durable runtime and research

This package starts the isolated Phase 3 durable runtime boundary. R32A defines
immutable state contracts. The package does not yet select a database, recover
operational state, call a broker, create orders, or authorize changes to
canonical administration data.

All numeric state that can be fractional uses `Decimal` through
`DurableDecimal`, with an explicit unit and an explicit ISO currency code for
currency values. Payloads are immutable, sorted, bounded, and reject floats,
mutable containers, and credential-like fields. Serialization and canonical
content hashes use the isolated R32B canonical JSON codec. The codec emits
UTF-8 bytes with sorted keys, normalized exact decimal text, explicit units
and currency, canonical UTC timestamps, strict schema decoding, and SHA-256
content hashes. It still performs no persistence or network I/O.

R32C adds a pure read authorization boundary. It reuses the Phase 2 role,
permission, feature entitlement, user status, and identity semantics; binds
every principal and account scope to one tenant; resolves only known accounts;
and denies missing authentication, cross-tenant access, unavailable grants,
unknown accounts, and scope violations. Tenant admin behavior is explicit and
still carries no canonical admin, execution, or production mutation authority.

R32D adds a pure account snapshot ingestion contract. It binds the Phase 2
snapshot to tenant, account, profile, source, currency, sequence, receipt time,
and freshness policy; requires complete risk and payout state; detects
inconsistent high-water and exposure data; and handles retries deterministically
as accepted, idempotent duplicate, or rejection. It returns only immutable
decisions and cursors and performs no write.

R32E adds a dedicated SQLite state store for Phase 3. It persists canonical
R32B bytes and their SHA-256 hashes in append-only state records, normalizes
tenant/account/user/profile identities behind foreign keys, and bootstraps a
checksummed schema and migration history. Writable handles use WAL,
`synchronous=FULL`, explicit transactions, and foreign-key enforcement. A
read-only reopen uses SQLite `mode=ro` plus `query_only`. Startup verifies the
database, store identity, schema version, bootstrap checksum, and migration
history. Reads revalidate both payload hashes and indexed identity columns.
The store never discovers, adopts, or migrates the legacy V8 database and
exposes no broker, execution, production mutation, or canonical admin authority.

R32F adds a forward-only migration framework for that isolated store. Migration
versions must be contiguous, immutable, checksum-stable, and limited to schema
creation or `ADD COLUMN` operations. Applied history and the cumulative schema
checksum are validated before any write. All pending steps, history receipts,
and the metadata version advance in one `BEGIN IMMEDIATE` transaction; any SQL
failure rolls the complete transaction back to the prior valid schema. Writable
startup applies pending registered migrations idempotently. Read-only startup
never migrates and fails closed when the file is behind the supported schema.

R32G adds the durable account snapshot repository. It stores the complete
immutable Phase 2 snapshot with exact tagged decimals, source timestamp offsets,
the original snapshot content hash, and a second hash over canonical Phase 3
bytes. Stream identity includes tenant, account, source version and simulation
mode, profile hash, and currency. Database uniqueness plus append-only triggers
enforce deterministic duplicate handling and prevent overwrite. New sequences
and capture times must advance monotonically. Reads support identity lookup,
latest, ordered history, and bounded half-open time ranges. Rejected ingestion
decisions return before a transaction and create no tenant, account, profile, or
snapshot rows. The repository remains read-only with respect to source accounts
and carries no execution or production mutation authority.

R32H adds an append-only evaluation repository linked by foreign key to the
durable snapshot and profile evidence. It preserves every V2 rule outcome,
blocking and failure reason, warning, exact computed metric, rule version, and
source-review status in deterministic hashed bytes. Authority is derived by the
repository: only a current verified source with no incomplete-data outcome can
be marked authoritative. Incomplete or unresolved evaluations remain durable
evidence with `authoritative=false`; callers cannot override that value. Reads
are tenant scoped, snapshot ordered, integrity checked, and carry no execution,
production mutation, or administrative authority.
