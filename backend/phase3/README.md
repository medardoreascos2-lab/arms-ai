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
