# ARMS AI - Fase 0.7: Durable crash recovery safety

## COMPLETED

Implemented synchronous durable checkpoints for the canonical PAPER runtime started with
`RuntimeLifecycleManagerV2.start_from(...)` / `StartupCoordinatorV2.startup_from(...)`.
The existing ASGI lifespan uses this entry point. No commit or push was performed.

Workspace: `C:/Development/ARMS-AI`.
Branch: `refactor/backend-architecture`.
Starting and final HEAD: `6808ed4231460245033b96132050704e2d0e1ee3`.
The pre-existing untracked root `AGENTS.md` and `docs/master/` were not modified.

## ROOT CAUSE

`ExecutionStateStoreV2.save_to_file()` was called by graceful shutdown and explicit callers.
There was no periodic checkpoint scheduler in the inspected canonical runtime. Abrupt process
termination bypassed the shutdown write, losing every subsequent in-memory mutation.

The previous snapshot contained active lifecycle positions, active protection/OCO records and
account/portfolio risk state (including closed portfolio positions). It omitted the canonical
`TradeJournalV2`, trade-history deduplication identities and PAPER orders, fills, positions and
client-order index. Those omissions prevented coherent continuation after recovery.
The existing SQLite `JournalDatabase` belongs to the separate legacy journal and does not
capture the canonical runtime's complete operational/risk state; it is not a suitable replay log.

At risk between writes: opens, partial/total closes, remaining quantities, cumulative realized
PnL, daily PnL/loss capacity, trading blocks, exposure, stop/target modifications, OCO terminal
states, pending execution records and journal/history entries.

Tests with persistence enabled also exposed synchronization defects: partial PnL arrived in
separate lifecycle steps; the monitor journal fallback could close an OPEN or unrelated trade;
explicit zero net PnL was treated as missing; the PAPER adapter could retain a locally closed
position as open. The scoped fixes make the checkpoint participants consistent.

## DURABILITY STRATEGY

1. Acquire an OS writer lock for the configured state path before startup recovery. Keep it for
   the runtime lifetime; competing writers fail closed. Use one reentrant lock for mutations,
   state capture and checkpoints, acquiring it before the account lock.
2. Validate the complete pre-operation state, then atomically write and fsync a `PENDING`
   record before allowing mutation. Nested lifecycle/portfolio/account/journal operations share
   the outer boundary; an entire monitor price update is one boundary.
3. Validate and persist a complete `COMMITTED` checkpoint synchronously before returning
   success. Include journal, history IDs, all protection/OCO records and PAPER execution records.
   Increment the generation and checksum canonical JSON with SHA-256; reject nonfinite JSON.
4. Write a same-directory temporary file, flush/fsync, then atomically replace the destination.
   POSIX also fsyncs the directory. On Windows the verified guarantee is abrupt process exit,
   not loss of power or failure of the underlying storage device.
5. Reject pending, empty, truncated, corrupt, inconsistent or incomplete state. Preserve the
   evidence; do not fall back to an older snapshot or overwrite the evidence during shutdown.
   Mark the account blocked and deny subsequent operational mutations after persistence/recovery
   failure. Refuse disabling recovery when a saved file exists or clearing the active file.
6. Restore complete records and cumulative account baselines without replaying executions,
   accounting callbacks or journal closes. Repeated recovery of identical state is a no-op;
   recovery over changed operational state fails. Existing risk blocks cannot be removed.

Legacy empty snapshots can migrate. Legacy snapshots with trading activity but missing canonical
journal/execution records require reconciliation; the implementation does not synthesize trades.
No new dependencies, background scheduler or event-sourcing architecture was introduced.

## FILES CHANGED

- `backend/account/account_state_manager_v2.py`
- `backend/execution/oco_manager_v2.py`
- `backend/execution/protective_order_registry_v2.py`
- `backend/journal/trade_journal_v2.py`
- `backend/portfolio/portfolio_manager_v2.py`
- `backend/services/durable_execution_state_v2.py`
- `backend/services/execution_state_store_v2.py`
- `backend/services/live_position_monitor_v2.py`
- `backend/services/runtime_lifecycle_manager_v2.py`
- `backend/services/startup_coordinator_v2.py`
- `backend/services/state_recovery_service_v2.py`
- `backend/services/trade_lifecycle_service_v2.py`
- `backend/tests/test_durable_crash_recovery_v2.py`
- `backend/tests/test_live_position_monitor_point_value_v2.py`
- `backend/tests/test_runtime_lifecycle_manager_v2.py`
- `backend/tests/test_startup_coordinator_v2.py`
- `backend/tests/test_state_recovery_service_v2.py`
- `docs/architecture/durable_crash_recovery_v2.md`

## TESTS EXECUTED

Final consolidated execution: Python 3.14.6, `pytest.main(paths + ['-q', '-p',
'no:cacheprovider', '--tb=short'])`, with the 40 exact paths listed below.
For app imports, the test process used `UNRELATED_REQUIRED_ENV` from
`backend.tests.test_partial_take_profit_policy_authority_v2`, plus
`ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS=20` and
`ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION=0.5`. These are explicit synthetic test settings;
no environment/configuration files or secrets were changed.

- `backend/tests/test_account_state_manager_v2.py`
- `backend/tests/test_asgi_runtime_integration_v2.py`
- `backend/tests/test_daily_pnl_safety_v2.py`
- `backend/tests/test_daily_session_reset_safety_v2.py`
- `backend/tests/test_dashboard_execution_manager_read_only_v2.py`
- `backend/tests/test_dashboard_execution_pipeline_read_only_v3.py`
- `backend/tests/test_dashboard_read_execution_safety_v2.py`
- `backend/tests/test_durable_crash_recovery_v2.py`
- `backend/tests/test_execution_state_store_v2.py`
- `backend/tests/test_graceful_shutdown_service_v2.py`
- `backend/tests/test_live_position_monitor_app_integration_v2.py`
- `backend/tests/test_live_position_monitor_break_even_v2.py`
- `backend/tests/test_live_position_monitor_broker_partial_close_sync_v2.py`
- `backend/tests/test_live_position_monitor_broker_protection_sync_v2.py`
- `backend/tests/test_live_position_monitor_partial_take_profit_v2.py`
- `backend/tests/test_live_position_monitor_point_value_v2.py`
- `backend/tests/test_live_position_monitor_portfolio_sync_v2.py`
- `backend/tests/test_live_position_monitor_realized_pnl_v2.py`
- `backend/tests/test_live_position_monitor_realtime_e2e_v2.py`
- `backend/tests/test_live_position_monitor_trade_learning_e2e_v2.py`
- `backend/tests/test_live_position_monitor_trailing_stop_v2.py`
- `backend/tests/test_live_position_monitor_v2.py`
- `backend/tests/test_portfolio_account_state_integration_v2.py`
- `backend/tests/test_portfolio_manager_v2.py`
- `backend/tests/test_runtime_lifecycle_manager_v2.py`
- `backend/tests/test_startup_coordinator_v2.py`
- `backend/tests/test_state_recovery_service_v2.py`
- `backend/tests/test_trade_accounting_safety_v2.py`
- `backend/tests/test_trade_lifecycle_app_integration_v2.py`
- `backend/tests/test_trade_lifecycle_broker_connector_integration_v2.py`
- `backend/tests/test_trade_lifecycle_close_sync_v2.py`
- `backend/tests/test_trade_lifecycle_exposure_integration_v2.py`
- `backend/tests/test_trade_lifecycle_oco_integration_v2.py`
- `backend/tests/test_trade_lifecycle_order_validation_integration_v2.py`
- `backend/tests/test_trade_lifecycle_portfolio_manager_integration_v2.py`
- `backend/tests/test_trade_lifecycle_portfolio_risk_integration_v2.py`
- `backend/tests/test_trade_lifecycle_protective_registry_integration_v2.py`
- `backend/tests/test_trade_lifecycle_risk_manager_integration_v2.py`
- `backend/tests/test_trade_lifecycle_service_v2.py`
- `backend/tests/test_trade_lifecycle_trade_journal_integration_v2.py`

## TEST RESULTS

**Final pre-commit review: 478 passed, 0 failed, 1 warning, 18.32 seconds.**
The same 40 files contain the original 467 tests plus 11 review regressions.
The warning is the installed Starlette/httpx deprecation; no dependency was changed.
`git diff --check` passed. Earlier runs exposed the monitor synchronization defect and outdated
isolated test doubles/identity fixtures; these were corrected and included in the final run.
An initial integration collection required the explicit test environment described above.

## CRASH RECOVERY VERIFIED

The new suite uses real child processes ending with `os._exit(23)` without graceful shutdown.

- A: open position, quantity, exposure, journal and protection/OCO restoration.
- B: partial close, remaining quantity and partial PnL, including the actual monitor path.
- C: full close, zero active exposure/protections, retained terminal records/history.
- D: realized loss restoring daily PnL, loss capacity and daily trading block.
- E: recovery before shutdown/any later snapshot; no periodic scheduler is assumed.
- F: repeated recovery on the same target and repeated fresh recoveries.
- G: empty/truncated files, checksum damage, orphan temporary file and interrupted operations.
- H: older explicit snapshot followed by newer partial/loss mutations; latest state survives.
- I: resume a recovered partial and close it without duplicate fills, closes or PnL.

Additional cases cover zero net PnL after partial, concurrent submissions, a second runtime writer,
fsync failure before execution, commit failure after mutation, crash during open/loss accounting,
independent daily block/protection updates, legacy migration/refusal and semantic corruption
with a recomputed checksum (missing/duplicate fills, missing journal timestamp, wrong protection
quantity, deleted risk block and a LIVE position in PAPER state).

## IDEMPOTENCY VERIFIED

No duplicated positions, journal/history rows, fills, realized/daily PnL or protection/OCO groups
in repeated recovery. Closed operations stay closed. Resumed partial accounting retains its
cumulative baseline and exact PAPER identifiers/client-order index.

## CORRUPTION SAFETY VERIFIED

Corrupt or in-flight persistence denies startup before operational restoration. No invented
positions/journal records or broker fills. Persistence failure blocks continued execution and
checkpoint overwrite. The stored evidence is preserved for reconciliation.

## RISK STATE RECOVERY VERIFIED

Daily loss, daily PnL, realized PnL, remaining loss capacity, trading blocks and portfolio state
are recovered together. Current risk blocks cannot be erased by an older unblocked snapshot.
The existing daily-session and read-only safety regression suites pass.

## DIFF SUMMARY

One small durability coordinator, checkpoint record extensions/validation, explicit mutation
boundaries and startup/shutdown wiring. Scoped synchronization fixes for partial accounting,
journal close identity/status, zero net PnL, and PAPER close state. New crash/fault tests and
updated lifecycle collaborator doubles. No real broker, LIVE enablement, read-side endpoint,
secret, account-switching or strategy changes.

## REMAINING ISSUES

- An interruption inside an operation leaves `PENDING` and requires operator reconciliation.
  Automatic completion/replay is deliberately refused when consistency cannot be established.
- Complete synchronous checkpoints cost two writes per outer operation and grow with retained
  journal/history. Storage performance and power-loss durability were not benchmarked/verified.
- Persistence is activated by the path-aware runtime startup. Standalone in-memory services and
  `start_clean()` without a persistence path do not acquire this durability guarantee.
- The legacy PAPER connector account summary is not the canonical accounting authority; its
  pre-existing balance/equity projection was not changed. Account/portfolio recovery uses
  `AccountStateManagerV2` and `PortfolioManagerV2`.
- No LIVE behavior or real broker was exercised. This is PAPER crash safety only.

## NEXT RECOMMENDED STEP

Define and independently validate an operator reconciliation procedure for `PENDING`/corrupt
snapshots before considering any LIVE rollout.


## FINAL PRE-COMMIT REVIEW

HEAD remains `6808ed4231460245033b96132050704e2d0e1ee3` on
`refactor/backend-architecture`. The exact 18-file list above is unchanged:
12 production files, 5 test files, 1 documentation file. No commit or push.

### Issues found and corrected

1. Memory recovery accepted a persisted `PENDING` envelope or invalid checksum because
   validation discarded its durability metadata. `validate_state()` now verifies any supplied
   persistence envelope before normalization, for file and memory recovery alike. Both cases
   were demonstrated by failing regressions before the fix.
2. A read-only `load_from_file()` advanced the store generation and thereby allowed an empty
   reader to overwrite a populated checkpoint. Reads now only retain source information;
   overwrite authority is adopted after successful reconstruction, or after this store writes
   a checkpoint. Manual saves compare the exact path, generation and content fingerprint under
   the writer lease. Cross-file and same-generation changed-file overwrites are refused.
   The original loss of positions was reproduced with a failing regression before the fix.
3. Manual snapshot saving cleared the `stopped` flag and could permit in-memory operations after
   shutdown. Saving now preserves the prior stopped state; a regression verifies zero fills.

### Sequence and atomicity

For an enabled durable runtime, `durable_mutation` returns the public result only after the
context manager exits successfully. Its outer boundary performs:

`validate baseline -> durable PENDING -> mutation -> validate complete state -> durable COMMITTED -> return`.

Nested participants return to the enclosing transaction; they do not commit individually.
A failed write/validation raises instead of returning outer success. Standalone services and
`start_clean()` without a persistence path remain explicitly outside this guarantee.

The write uses a same-directory temporary file, binary write, flush, fsync and `os.replace`;
POSIX also fsyncs the directory. SHA-256 covers canonical JSON plus phase/generation. The runtime
holds an OS writer lease and a reentrant mutation/checkpoint lock. Generations advance for
commits, and manual overwrite also requires matching provenance/fingerprint. Storage rollback
by an external actor and physical power loss are not claimed to be detectable/prevented.

### Exact crash window matrix

| Window | Persisted evidence | Recovery |
|---|---|---|
| A: before PENDING write | Previous COMMITTED | Restore previous state; mutation has not started. |
| B: after durable PENDING, before mutation | PENDING | Fail closed; no automatic commit/discard. |
| C: during mutation | PENDING | Fail closed; reconcile interrupted operation. |
| D: after mutation, before COMMITTED | PENDING; possibly temporary file | Fail closed; do not restore baseline as current. |
| E: after durable COMMITTED, before return | New COMMITTED | Restore new state exactly once, although caller may not have received success. |

The five boundaries are tested using child-process `os._exit(23)` fault injection. A crash during
construction of either temporary file additionally leaves incomplete evidence and fails closed.
COMMITTED is the complete checkpoint and its phase marker written together; there is no separate
commit-marker update that could certify a different payload.

### Final checks

- Original 467 tests plus 11 regressions: **478 passed** in the same 40 test files.
- One existing Starlette/httpx deprecation warning.
- `git diff --check`: passed.
- Repeated recovery keeps cumulative realized/daily PnL, fills, positions, journal/history,
  OCO/protections and terminal state without replaying accounting or execution side effects.
- PENDING/corrupt state is not automatically discarded/promoted and blocks operational mutation.
- No LIVE activation, real broker connector changes, secrets, account switching or read-side
  endpoint edits. Shared lifecycle/accounting code is covered in PAPER only.
- All changes belong to Phase 0.7 persistence, consistency, safety tests or its documentation.

**READY FOR COMMIT: YES, for the documented PAPER runtime with durability enabled.**
No commit has been performed. The documented reconciliation and deployment limitations remain.
