# Phase 5 synthetic combined failure drill (R60C)

This exact order covers a synthetic database outage, worker crash, scheduler
failover, authentication key rotation, queue backlog, research overload, and
isolated backup restore. It grants no external, production, execution, broker,
PAPER, or LIVE authority. Health remains blocked pending operator release.

## Recovery order

1. `ASSERT_SYNTHETIC_SCOPE`
2. `DECLARE_COMBINED_INCIDENT`
3. `BLOCK_EXECUTION_AND_MUTATIONS`
4. `CONTAIN_DATABASE_OUTAGE`
5. `QUIESCE_AND_RESTART_WORKER`
6. `FAIL_OVER_SCHEDULER_LEASE`
7. `ROTATE_AUTH_CREDENTIAL_REFERENCE`
8. `BOUND_QUEUE_BACKLOG`
9. `THROTTLE_RESEARCH_OVERLOAD`
10. `SELECT_VERIFIED_BACKUP`
11. `RESTORE_TO_ISOLATED_DESTINATION`
12. `VERIFY_HASH_SCHEMA_AUDIT_TENANTS_PROVENANCE`
13. `RECONCILE_WORKERS_SCHEDULER_QUEUE`
14. `VERIFY_TRUTHFUL_BLOCKED_HEALTH`
15. `REQUIRE_OPERATOR_RELEASE`

A missing, reordered, or additional action fails the drill. Each of the eight
evidence checks must pass independently. Sequence success is test evidence only;
it never proves production recovery or grants operator release.
