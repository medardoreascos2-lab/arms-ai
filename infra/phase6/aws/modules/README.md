# Phase 6 AWS modules

Provider-specific resources are divided into modules for network, database,
secrets, identity, observability, backup, registry and workloads. Modules expose
only non-secret identifiers and narrow references needed by their consumers.
They do not configure a state backend and must never contain secret values.
