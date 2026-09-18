# Phase 1 recovery / CLI baseline closure

Package baseline: `f19aa6f0e016e71377577e239a23f758e9ed08ed` on
`refactor/backend-architecture`, fetched and verified equal to remote with no
tracked changes or staged content. All 83 unrelated untracked files were hashed
before work and must remain unchanged. PH1-REQ-009 files are outside this diff.

## Verified root causes

The exact 12 node IDs and exception signatures recorded by PH1-REQ-009 reproduced
at this package's current synchronized baseline, with literal signature equality.
Before production changes, the five committed `test_ph1_req008*` modules and
related recovery/startup/CLI-owner modules passed 159 tests.

| Cluster | Classification | Initial failures | Evidence and correction |
|---|---|---:|---|
| Pending crash windows | CONTRACT_EVOLUTION | 6 | Old tests expected every PENDING checkpoint to fail with ValueError. PH1-REQ-008 instead reconciles verified evidence: PREPARED resolves without execution; COMPLETED restores the proven result; partial/ambiguous results fail startup with RuntimeError. Assertions now check this distinction, exact partial evidence, disabled durability, unchanged files, no additional execution, and repeat-recovery idempotence. |
| Unsigned legacy startup | TEST_EXPECTATION_DEFECT | 2 | Automatic startup's applicability boundary requires an intact durable envelope. Legacy validation remains available through explicit recovery. Tests now exercise explicit offline validation/migration before startup; additional tests require unsigned empty and operational snapshots to fail automatic startup without restoration. Missing journal activity is never invented. |
| CLI integration fixture | TEST_HARNESS_DEFECT | 3 | FakeRuntimeContext lacked the coordinator used by the committed CLI. The fixture now models persisted-state startup through the existing lifecycle wrapper, preserving pipeline-error shutdown and startup-error non-dispatch assertions. |
| Semantic incompatibility fixture | TEST_HARNESS_DEFECT | 1 | The fixture passed an old checksum into seal(), creating an invalid envelope instead of valid-checksum, semantically incompatible state. Removing the old checksum reaches PAPER/LIVE semantic validation and retains the failed-recovery report and zero-execution assertions. |
| CLI startup and shutdown wiring | PRODUCTION_DEFECT | Independently demonstrated during review | Ten new real-owner CLI probes failed before the patch. Clean startup skipped saved-state applicability/reconciliation/recovery and left RuntimeLifecycleManagerV2 IDLE, so its shutdown rejected the call and could mask a pipeline error. The CLI now calls the existing lifecycle_manager.start_from(snapshot_path). |

The initial 12 do not all imply production defects. The CLI defect is separately
demonstrated by behavior tests, not inferred from the obsolete fixture failures.

## Canonical ownership and safety

The unchanged production delegation is:

`build_runtime_context` -> `RuntimeLifecycleManagerV2.start_from` ->
`StartupCoordinatorV2.startup_from` ->
`StateRecoveryServiceV2.pending_reconciliation_required` -> conditional
`reconcile_pending_from` -> `recover_from` -> durability enable.

The lifecycle wrapper records RUNNING after successful startup and delegates
shutdown to the existing graceful shutdown service. No second recovery algorithm
or persistence migration was added. The sole production change selects this
existing path in the CLI and supplies the configured snapshot path.

COMMITTED checkpoints skip pending reconciliation. PENDING checkpoints require
reconciliation before ordinary recovery. Ambiguous/corrupt states restore no
phantom activity. A consistent partial prefix may be reconstructed from its
operation-bound evidence, including existing positions and fills, but startup
fails and the runtime remains blocked. Reconstruction is distinct from new
execution: tests compare all participants to evidence and forbid execution and
accounting callbacks. Unsafe startup never enables durability, starts the CLI
pipeline/connector, or overwrites evidence through shutdown.

Crash-window tests retain the two historical parameter IDs containing `False-0`
so the exact original failing nodes remain selectable; those IDs are historical
identifiers, while the explicit parameter values now encode the proven outcome.

The existing full crash/reconciliation tests continue to protect committed
positions, orders/fills, protection/OCO, partial PnL, risk blocks, generation,
checksum integrity, writer exclusivity, and idempotence. The new CLI tests also
exercise the actual runtime factory through clean startup and restart. External
market/pipeline work is stubbed; all operational recovery evidence is PAPER.
No LIVE execution or real broker capability is enabled or claimed.

## Exact scope

| File | Why required |
|---|---|
| `backend/main.py` | Route CLI startup through the existing persisted-state lifecycle wrapper; preserve canonical coordinator ownership and valid shutdown state. |
| `backend/tests/test_durable_crash_recovery_v2.py` | Correct pending/legacy expectations and strengthen evidence, blocked-state, durability, generation, and idempotence assertions. |
| `backend/tests/test_main_runtime_integration.py` | Align CLI fakes with persisted-state startup and verify no external dispatch after startup failure. |
| `backend/tests/test_phase1_recovery_characterization_v2.py` | Fix the checksum fixture so semantic incompatibility is actually tested. |
| `backend/tests/test_rec003_cli_startup_owner_v2.py` | Require the persisted-state wrapper and prohibit clean-start/direct-recovery bypasses. |
| `backend/tests/test_phase1_asgi_cli_equivalence_v2.py` | Update the entrypoint characterization to the same canonical persisted-state path. |
| `backend/tests/test_recovery_cli_pending_contract_v2.py` | Exercise real recovery/lifecycle owners, crash evidence, startup ordering, fail-closed pipeline admission, safe shutdown, and actual runtime-factory restart. |
| `docs/architecture/phase1_recovery_cli_baseline_closure_v3.md` | Record baseline attribution, root causes, scope, safety boundaries, and validation evidence for this separate package. |

## Reproducible validation

All broad test runs use the existing legitimate repository PAPER policy in the
test process only. No production defaults, credentials, or risk policy changed.

```powershell
python -c "import os,sys,pytest; from backend.tests.test_account_switch_safety_containment_v2 import POLICY; os.environ.update(POLICY); sys.exit(pytest.main(sys.argv[1:]))" -q -p no:cacheprovider --tb=short backend/tests
```

For exact reproduction at the baseline, select the following recorded node IDs
with the same runner. The current package must pass those same 12 IDs.

| Exact baseline node ID | Exception type / message |
|---|---|
| `backend/tests/test_durable_crash_recovery_v2.py::test_corrupt_or_inflight_state_fails_closed[pending]` | `RuntimeError`: Pending operation reconciliation did not resolve to a safe startup state. |
| `backend/tests/test_durable_crash_recovery_v2.py::test_corrupt_or_inflight_state_fails_closed[pending_open]` | `RuntimeError`: Pending operation reconciliation did not resolve to a safe startup state. |
| `backend/tests/test_durable_crash_recovery_v2.py::test_corrupt_or_inflight_state_fails_closed[pending_loss]` | `RuntimeError`: Pending operation reconciliation did not resolve to a safe startup state. |
| `backend/tests/test_durable_crash_recovery_v2.py::test_legacy_snapshot_with_missing_journal_is_not_invented` | `AssertionError`: Regex pattern did not match.   Expected regex: 'Legacy snapshot lacks'   Actual message: 'Evidence checksum mismatch.' |
| `backend/tests/test_durable_crash_recovery_v2.py::test_empty_legacy_snapshot_migrates_without_inventing_activity` | `ValueError`: Evidence checksum mismatch. |
| `backend/tests/test_durable_crash_recovery_v2.py::test_exact_crash_window_matrix[window_after_pending-PENDING-False-0]` | `Failed`: DID NOT RAISE ValueError |
| `backend/tests/test_durable_crash_recovery_v2.py::test_exact_crash_window_matrix[pending_open-PENDING-False-0]` | `RuntimeError`: Pending operation reconciliation did not resolve to a safe startup state. |
| `backend/tests/test_durable_crash_recovery_v2.py::test_exact_crash_window_matrix[window_before_committed-PENDING-False-0]` | `Failed`: DID NOT RAISE ValueError |
| `backend/tests/test_main_runtime_integration.py::test_main_starts_and_stops_runtime` | `AttributeError`: 'FakeRuntimeContext' object has no attribute 'startup_coordinator' |
| `backend/tests/test_main_runtime_integration.py::test_main_stops_runtime_when_pipeline_fails` | `AttributeError`: 'FakeRuntimeContext' object has no attribute 'startup_coordinator' |
| `backend/tests/test_main_runtime_integration.py::test_main_does_not_shutdown_when_startup_fails` | `AttributeError`: 'FakeRuntimeContext' object has no attribute 'startup_coordinator' |
| `backend/tests/test_phase1_recovery_characterization_v2.py::test_incompatible_recovery_is_rejected_and_execution_remains_blocked` | `TypeError`: 'NoneType' object is not subscriptable |

Direct certification uses these 22 files:

- `backend/tests/test_ph1_req008_pending_applicability_v2.py`
- `backend/tests/test_ph1_req008_startup_behavior_v2.py`
- `backend/tests/test_ph1_req008_startup_pending_fail_closed_v2.py`
- `backend/tests/test_ph1_req008_startup_pending_order_v2.py`
- `backend/tests/test_ph1_req008_startup_pending_recovery_v2.py`
- `backend/tests/test_state_recovery_service_v2.py`
- `backend/tests/test_pending_operation_reconciliation_v2.py`
- `backend/tests/test_startup_coordinator_v2.py`
- `backend/tests/test_recovery_consistency_v2.py`
- `backend/tests/test_phase1_recovery_execution_blocking_v2.py`
- `backend/tests/test_rec003_cli_startup_owner_v2.py`
- `backend/tests/test_durable_crash_recovery_v2.py`
- `backend/tests/test_main_runtime_integration.py`
- `backend/tests/test_phase1_recovery_characterization_v2.py`
- `backend/tests/test_recovery_cli_pending_contract_v2.py`
- `backend/tests/test_phase1_asgi_cli_equivalence_v2.py`
- `backend/tests/test_runtime_lifecycle_manager_v2.py`
- `backend/tests/test_runtime_context_v2.py`
- `backend/tests/test_runtime_context_app_integration_v2.py`
- `backend/tests/test_graceful_shutdown_service_v2.py`
- `backend/tests/test_execution_state_store_v2.py`
- `backend/tests/test_asgi_runtime_integration_v2.py`

## Validation results

- Initial exact-node reproduction: **12 failed**, matching every previously
  recorded node ID, exception type, and exception message.
- Prepatch PH1-REQ-008 and related recovery/CLI-owner gate: **159 passed**.
- Ten new real-owner CLI probes before the production patch: **10 failed**,
  demonstrating clean-start bypass and IDLE shutdown rejection.
- Repaired original node IDs: **12 passed**.
- Final direct gate across the 22 files above: **297 passed**.
- Full backend with the same repository PAPER policy: **5,306 passed, zero
  failed, one skipped**. The known pytest plugin-import warnings remain.
- `python -m py_compile` passed for all seven modified/new Python files.
- `git diff --check` passed; the eight-file diff was reviewed against baseline.
- Publication requires exact explicit-path staging, `git diff --cached --check`,
  and a repeat of the 297-test direct gate with unchanged staged content.

## Remaining boundary

This closes the recovery/CLI baseline-failure package, not the entire Phase 1
program. Automatic startup intentionally does not infer an unsigned legacy
snapshot's safety. Explicit legacy recovery still rejects missing execution
history. The separately documented legacy market endpoint ownership/availability
gap remains the next evidenced Phase 1 follow-up; PH1-REQ-009 is unchanged.
