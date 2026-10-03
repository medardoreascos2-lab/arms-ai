# Phase 3 durable runtime and research

This package starts the isolated Phase 3 durable runtime boundary. R32A only
defines immutable state contracts. It does not select a database, perform I/O,
recover operational state, call a broker, create orders, or authorize changes
to canonical administration data.

All numeric state that can be fractional uses `Decimal` through
`DurableDecimal`, with an explicit unit and an explicit ISO currency code for
currency values. Payloads are immutable, sorted, bounded, and reject floats,
mutable containers, and credential-like fields. Serialization and canonical
content hashes are intentionally deferred to R32B.
