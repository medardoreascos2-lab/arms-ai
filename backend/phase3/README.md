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
