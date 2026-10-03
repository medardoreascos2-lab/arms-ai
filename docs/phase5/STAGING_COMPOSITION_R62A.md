# Phase 5 isolated local staging composition (R62A)

The R62A composition binds the existing read-only API, isolated SQLite durable
store, transport authorization, replay protection, provider-neutral secret
interface, worker and scheduler supervisors, in-memory metrics, alert policy,
local backup and isolated restore controls, authenticated local-test backup
cipher, and research queue.

Composition is inert. It starts no process, opens no PostgreSQL connection,
contacts no provider, routes no external notification, and performs no backup or
restore. The local database must resolve inside an existing non-symlink runtime
root, and every component must carry zero execution or external authority.

The runtime reports `HOLD`. Its fixed authority flags deny external traffic,
external delivery, broker access, PAPER trading, LIVE trading, production
mutation, deployment, and execution. PostgreSQL, managed identity, managed
secrets, external telemetry, and external backup controls remain provider
blockers; local composition does not claim cloud equivalence.
