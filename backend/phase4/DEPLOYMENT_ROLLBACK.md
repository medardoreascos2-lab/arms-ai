# Phase 4 Deployment Rollback Contract

## Safety declarations

APPLICATION_ROLLBACK != DATABASE_ROLLBACK

AUTOMATIC_REVERSE_MIGRATIONS: PROHIBITED

DATABASE_RESTORE: MANUAL_ESCALATION_ONLY

LIVE_TRADING_ENABLEMENT: OUT_OF_SCOPE

OPERATOR_RELEASE_REQUIRED: TRUE

This runbook is a decision and evidence contract. It does not authorize a deployment, a rollback, a database mutation, a broker connection, or LIVE trading. An operator must approve each operational transition through the environment's independent change process.

## Entry criteria

A rollback may be considered only when the current release has a verified operational defect and remaining on that release has greater documented risk than returning to a known artifact. Before any change:

1. Stop new state-changing admission and place schedulers in a controlled paused state.
2. Record the incident, affected environment, tenants, accounts, release manifest SHA, database schema version, worker generations, feature flags, and the reason for rollback.
3. Preserve logs, metrics, health reports, audit evidence, and the current configuration references.
4. Confirm account, portfolio, journal, outbox, and risk state are internally consistent. An unexplained mismatch blocks application rollback and requires incident escalation.
5. Create and validate a new backup under the Phase 4 backup and isolated restore contracts. A backup is evidence; it does not authorize restoration.

## Previous application artifact

The candidate previous artifact must have a canonical Phase 4 build manifest. Verify its full Git SHA, manifest SHA, dependency pins, feature flags, migration version, and every artifact hash. The artifact must come from the approved artifact store and must not be rebuilt from an uncommitted worktree.

Reject the candidate if any manifest field is missing, any hash differs, its origin is uncertain, or it contains a feature that was never approved for the target environment.

## Compatible schema range

Each application artifact must declare the minimum and maximum database schema versions it can read and write. Compare that closed range with the observed database version before switching application artifacts.

Application rollback is allowed only when the observed schema version is within the previous artifact's declared compatible range. A schema newer than that range blocks application rollback. Use a forward-compatible application fix or a separately reviewed forward migration instead.

Application rollback never lowers the database schema version. Phase 4 migrations are forward only. Do not run an automatic down migration, destructive reverse migration, or data rewrite to make an older application appear compatible.

## Feature flag rollback

Disable the smallest implicated Phase 4 feature first when doing so contains the incident. Record the old and new flag set and confirm that disabling the feature cannot bypass authentication, tenant isolation, risk controls, audit recording, or market-data freshness rules.

Feature flags may reduce optional capability. They must never enable LIVE trading, execution authority, production mutation authority, weaker authorization, or weaker risk limits during rollback.

## Worker rollback

1. Stop scheduler claims so no new durable work is admitted.
2. Allow active workers to finish or reach their defined safe shutdown deadline.
3. Record outstanding leases, retry records, dead letters, audit events, and outbox state.
4. Confirm no worker from the current generation remains active before starting the previous generation.
5. Start one previous-version worker in observation mode and verify database compatibility, lease ownership, health, and backlog behavior.
6. Increase worker count only after the operator accepts the evidence. Never replay completed execution, accounting, notification, or research side effects.

If worker ownership, durable cursors, or idempotency evidence is ambiguous, keep workers stopped and escalate.

## Application rollback procedure

1. Verify all entry criteria and the previous artifact manifest.
2. Confirm the database schema is inside the artifact's compatible range.
3. Capture the current deployment identity and retain the current artifact for forward recovery.
4. Apply the reviewed feature flag rollback and quiesce workers as described above.
5. Replace only the application artifact through the environment's authorized release mechanism.
6. Start with state-changing operations blocked. Verify configuration references, authentication, tenant/account isolation, database health, migration state, metrics, audit continuity, and read-only health behavior.
7. Reconcile durable queues and worker generations without inferring or replaying missing trading effects.
8. Require explicit operator release before restoring any state-changing Phase 4 operation.

## Database restore escalation

Database restore is a separate disaster recovery operation and is never an automatic consequence of application rollback. Escalation requires all of the following:

- verified corruption or loss that cannot be resolved through a forward repair;
- a completed, checksum-valid backup and isolated restore validation report;
- documented recovery point and recovery time impact;
- documented expected data loss and affected tenant/account scope;
- maintenance window and independent operator approval;
- a new preservation backup of the damaged state when it can be captured safely;
- a post-restore plan for account, portfolio, journal, audit, outbox, and risk reconciliation.

Never restore over an active database. Keep application writers, schedulers, workers, and retry operations blocked until the restored state is independently reconciled. A successful file restore does not prove operational recovery.

## Abort and escalation criteria

Abort the rollback and keep state-changing operations blocked when any artifact hash fails, schema compatibility is unknown, a required secret reference is unavailable, worker leases are ambiguous, durable records disagree, backup validation fails, or tenant/account scope cannot be proven.

Escalation must preserve the original evidence and identify the exact failed criterion. Do not substitute simulated, demo, fixture, or hardcoded state for missing production evidence.

## Completion evidence

The rollback record must include:

- incident and operator identities;
- previous and replacement build manifest SHAs;
- observed database schema version and declared compatible range;
- before/after feature flags;
- before/after worker generations and lease evidence;
- health, metrics, audit, outbox, account, portfolio, and risk reconciliation results;
- backup and isolated restore validation identifiers when restore escalation occurred;
- explicit operator release or a continuing blocked status.

Rollback is complete only when the application artifact is verified, operational state is reconciled, safety gates remain fail closed, and the operator records release. No outcome in this document certifies LIVE trading.
