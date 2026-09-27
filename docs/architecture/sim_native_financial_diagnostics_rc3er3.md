# RC3E-R3 financial failure diagnostics

The original ENTRY assertion (`OPEN` expected, `UNAVAILABLE` observed) remains
**HISTORICAL_UNROOTED_NO_ARTIFACTS**. The original exception and retained test
directory are unavailable. Successful repetitions cannot establish a past cause.
No Windows locking, ordering, timing, or financial defect is asserted as that cause.

## Exception boundaries

`SimNativeFinancialRuntimeServiceV3.start()` and `observe()` latch the published
view to UNAVAILABLE, record sanitized failure evidence, release the checkpoint
lease, and disable ingestion on an exception. `NativeSimFinancialCheckpointV3.start()`
also fails durability closed and releases its lease. The shared durability mutation
boundary retains its original rules: an incomplete body rolls back to its baseline;
failure after completion preserves the PENDING fence and requires reconciliation.
An exception during rollback must not replace the first recorded inner failure.

| Stage | Observed boundary |
| --- | --- |
| SERVICE_START | Identity, policy, path and composition failures outside a finer scope |
| AUTHORITY_LOAD | Existing authority key loading; no provisioning |
| CONFIG_VERIFY | Authenticated configuration read, verification, expiry and approved paths |
| RUNTIME_BUILD | Canonical isolated native financial runtime construction |
| CHECKPOINT_START | Checkpoint path preflight, incomplete temporary/orphan evidence checks |
| CHECKPOINT_OPEN | Lease acquisition and persisted checkpoint read/JSON decode |
| CHECKPOINT_VERIFY | Checkpoint checksum, committed generation and state validation |
| CHECKPOINT_RESTORE | Restore validated participants and verify reconstructed state |
| CHECKPOINT_COMMIT | Existing durable checkpoint finalization, including fsync/replace |
| PHASE_DISCOVERY | Sorted native phase enumeration |
| PHASE_READ | Native phase bytes read |
| PHASE_VERIFY | Authenticated phase preflight and batch consistency checks |
| PHASE_APPLY | Financial application and transaction body; fallback reconciliation boundary |
| RECEIPT_WRITE | Immutable authenticated checkpoint receipt creation |
| PROJECTION_APPLY | Startup projection reconstruction and dashboard consumer delivery |
| OUTBOX_DELIVERY | Delivery acknowledgment and durable acknowledgment transaction |
| SERVICE_PUBLISH | Final receipt/state/projection validation and immutable observation capture |

An equivalent future ENTRY failure is diagnosable across these boundaries. There
is insufficient evidence to select one stage as the historical cause. A stage is
an observed failure boundary, not proof of the underlying OS or hardware cause.
The shared checkpoint helpers only observe an active context owned by this native
financial service. They neither write diagnostics nor change PAPER behavior on
their own. Context is reset on every exit and separate across threads/contexts.

The strict risk-authority inventory detected four changed method fingerprints:
`DurableExecutionStateV2.mutation`, `NativeSimFinancialCheckpointV3.start`, and
`NativeSimIntegrationV3.reconcile` / `_publish_dashboard`. Removing only the new
diagnostic scopes/import/generation observations reproduces each previously
approved AST fingerprint exactly (4/4). Only those four source hashes and call
lists are refreshed in the inventory. All 219 authority identities, classifications,
flags, thresholds, block writers/clearers, and the inventory test remain unchanged.

GET remains memory-only. A stale/expired snapshot returns UNAVAILABLE without
filesystem writes. Explicit stop similarly does not manufacture failure evidence.
Startup and worker exceptions, rather than normal read freshness or shutdown,
are the durable diagnostic boundary. Process termination without an exception
reaching a handler cannot be captured by a Python exception observer.

## Diagnostic contract and durability

Schema: `SIM_NATIVE_FINANCIAL_DIAGNOSTIC_V3`. Fixed fields:
`schema`, `observed_at`, `stage`, `status`, `error_code`, `exception_type`,
`runtime_generation`, `configuration_generation`, `native_phase_generation`,
`checkpoint_present`, `projection_present`.

Stages and `STAGE_FAILED` codes are closed enumerations. Exception types are mapped
to a fixed built-in allowlist; messages and custom class names are excluded.
Generations are bounded nonnegative integers or null. Native phase generation is
the last authenticated phase observed in the current operation, if known; it does
not certify application or commitment. Presence can be null when inaccessible.
No paths, admission wire, keys, credentials, environment or arbitrary metadata
are serialized. Diagnostics grant no execution or financial authority.

The canonical authority root contains the separate bounded artifact
`diagnostics/financial-latest-failure.json`. It is not a checkpoint or projection.
An exclusive fixed temporary file, flush, fsync and atomic replacement protect
the last complete artifact. The writer removes only its own temporary file;
pre-existing collision evidence is preserved. A later failure replaces the latest
failure; a successful startup does not write or erase it. No accumulating history
is created. The first inner exception survives propagation/rollback exceptions.

If the diagnostic path itself is inaccessible, redirected, full, locked, or has a
stale temporary file, disk persistence cannot be guaranteed. The service remains
UNAVAILABLE, retains the bounded diagnostic in memory, and exposes an internal
`write_status=FAILED`. The previous complete diagnostic remains. This limitation
is explicit; no health grant or automatic financial repair follows from logging.

## Offline fault and filesystem certification

The new diagnostic tests inject checkpoint open/verify/restore, phase enumeration,
read/HMAC/apply, commit, receipt, projection replace, and acknowledgment failures.
Additional tests cover authority/configuration/build/publication failures,
mid-application journal rollback, nested rollback exceptions, bounded sanitization,
and diagnostic storage failures. Restart must either restore exactly one financial
and projection effect or remain fenced without modifying financial authority.

| Windows-local case | Classification after isolated obstacle is removed |
| --- | --- |
| Existing valid destination | RECOVERABLE_ON_RESTART (atomic replacement remains valid) |
| Missing diagnostic parent | RECOVERABLE_ON_RESTART (independent parent creation) |
| Read-only projection | EXPECTED_FAIL_CLOSED; RECOVERABLE_ON_RESTART |
| Checkpoint temporary collision | OPERATOR_REVIEW_REQUIRED; existing fence retained |
| Projection held by Win32 handle denying sharing | EXPECTED_FAIL_CLOSED; RECOVERABLE_ON_RESTART |
| Projection replace failure | EXPECTED_FAIL_CLOSED; RECOVERABLE_ON_RESTART |
| Interrupted projection temporary write | RECOVERABLE_ON_RESTART from financial authority |
| Stale unlocked checkpoint lock file | RECOVERABLE_ON_RESTART (lock ownership, not filename, governs) |
| Checkpoint lock held by another owner | EXPECTED_FAIL_CLOSED; RECOVERABLE_ON_RESTART after release |

The suite never clears a checkpoint fence to make a test pass. Partial financial
commit and mid-body failure remain unavailable on repeated restart when existing
recovery rules require operator review. Actual Windows read-only attributes and
Win32 deny-sharing handles are used; replace exceptions are also injected at
deterministic boundaries. Tests use synthetic authority and an offline C# SDK
harness, never NinjaTrader, production spools, DPAPI provisioning or native orders.

Randomized cases use seeds 31000 through 31049 inclusive, unique pytest temporary
roots and fresh runtime/projection objects. Each exercises a restart before replay,
after financial checkpoint, or after projection, followed by shuffled restart,
old-phase replay, duplicate delivery, existing receipt and existing event-ID cases.
Financial effects and durable projection effects are exactly once by stable ID;
event transport remains **AT_LEAST_ONCE**.

The separate ENTRY campaign uses the existing exact node
`test_authenticated_bridge_replay_restart_and_projection_once[valid-ENTRY-0-1]`
in 100 serial fresh interpreter processes and fresh basetemp roots. It verifies
released leases and removes only its successfully completed owned temporary root.
Any failure stops the campaign and retains that root and diagnostic evidence.
Five serial RC3E-focused suite repetitions then certify regression stability.
Gate outcomes and interpreter identity belong in the execution report; this
document does not assert that an unexecuted campaign has passed.

Native submit and automatic retry remain disabled. No deployed source, signed
configuration, authority, risk/news/probability gate or financial policy changes
are part of this patch. Production no-order acceptance and push are separate gates.

## Executed offline certification

Interpreter: existing CPython 3.14.6, MSC v.1944 AMD64; Windows 10 build 19045;
pytest 9.1.1. All Python runs used the same existing executable directly with `-B`,
`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, the existing process-local RC3E
test profile and isolated LOCALAPPDATA. No launcher, installation or new virtual
environment was used.

- Exact ENTRY scenario: **100/100 consecutive PASS**, distinct fresh processes
  and basetemp roots, no parallel workers, released leases and owned-root cleanup
  verified after every successful run.
- Required injected fault boundaries: **11/11 PASS**; additional startup,
  publication, rollback, sanitization and diagnostic-storage regressions pass.
- Actual Windows filesystem cases: **9/9 PASS**, with classifications above.
- Seeded restart/order scenarios: **50/50 PASS**, seeds 31000–31049 inclusive;
  these also run in every full suite repetition.
- Full RC3E suite: **563 PASS in each of five consecutive runs** (248.70, 253.98,
  252.46, 247.43 and 246.65 seconds). No failures or skips in those five runs.
- Frontend: **49 PASS**; `npm.cmd run lint` and `npm.cmd run build` pass.
- Financial/projection effects remain exactly once; transport remains at least
  once. B1/B2/B3, PAPER isolation and read-only financial/dashboard APIs pass.

Before the consecutive campaign, a development suite stopped at 481 passed / one
failure because the strict risk inventory detected diagnostic instrumentation.
The four reviewed evidence entries were updated as described above; the test was
not relaxed. Production code remained byte-identical to the 100-run ENTRY campaign.
The historical unexplained ENTRY incident is separate and remains unrooted.
The existing Starlette/httpx deprecation warning is non-blocking; no dependency
was installed to suppress it.

The five-run pytest module list was:

```text
backend/tests/test_sim_native_financial_runtime_service_v3.py
backend/tests/test_sim_native_financial_projection_v3.py
backend/tests/test_sim_native_financial_checkpoint_v3.py
backend/tests/test_sim_native_integration_v3.py
backend/tests/test_sim_native_account_authority_v3.py
backend/tests/test_trade_lifecycle_dashboard_event_publisher_v2.py
backend/tests/test_asgi_runtime_integration_v2.py
backend/tests/test_account_runtime_transition_v2.py
backend/tests/test_account_switch_api_v2.py
backend/tests/test_sim_native_dashboard_reader_v3.py
backend/tests/test_dashboard_read_execution_safety_v2.py
backend/tests/test_dashboard_live_api_v2.py
backend/tests/test_phase1_risk_precedence_v5.py
backend/tests/test_sim_native_financial_diagnostic_v3.py
```

The frontend test command was:

```text
node --test src/lib/dashboardApi.test.mjs src/lib/dashboardConnection.test.mjs src/lib/dashboardProjection.test.mjs src/lib/paperRcProjection.test.mjs src/components/dashboard-v2/SimNativeRuntimeCard.test.mjs src/components/dashboard-v2/SimNativeFinancialCard.test.mjs
```

No native order submission, cancellation, flattening, authority/config publication,
deployed source change, automatic platform start, or production restart was performed.
Both `NATIVE_SUBMIT_ENABLED` and `AUTO_RETRY_ALLOWED` remain false. Independent
push review and production no-order acceptance remain separate, unperformed gates.
