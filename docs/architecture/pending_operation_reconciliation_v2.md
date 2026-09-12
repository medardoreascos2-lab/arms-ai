# Phase 0.8 — Pending operation reconciliation (PAPER only)

## Scope and root cause

Workspace: `C:/Development/ARMS-AI`; branch: `refactor/backend-architecture`.
Starting HEAD: `8dac83f666f4f0e126bd9d2c8d933200920e73de`.
No commit or push. Existing untracked root `AGENTS.md` and `docs/master/` are untouched.

Phase 0.7 atomically overwrites the checkpoint with a PENDING **baseline** before
executing an operation. The canonical PAPER broker, journal, portfolio, account,
protections and OCO participants live in memory until the final checkpoint.
The baseline alone cannot distinguish an operation that never entered its body
from one that filled, partially closed, or completed before a process exit.
Legacy SQLite journal records belong to a different execution path and cannot
establish the missing canonical identities/accounting.

**AN AMBIGUOUS PENDING OPERATION MUST NEVER BE GUESSED.**

## Explicit model

| Status | Required evidence | Restoration and execution policy |
| --- | --- | --- |
| `CONFIRMED_NOT_EXECUTED` | Matching PREPARED evidence, identical to the baseline, before durable STARTED; or a completed operation with identical operational state | Restore the baseline exactly, close PENDING atomically; create no position, fill or PnL |
| `CONFIRMED_EXECUTED` | Matching COMPLETED evidence with a complete, consistent participant set and no outstanding order | Restore the exact recorded result and atomically replace PENDING with COMMITTED |
| `PARTIALLY_EXECUTED` | Latest OBSERVED evidence is a consistent changed participant set, or a complete observation contains a submitted/partially filled order | Restore only that demonstrated state, retain PENDING, block all further mutations |
| `AMBIGUOUS` | Missing/stale evidence, STARTED without a later observation, conflicting participants or incompatible current risk blocks | Preserve evidence, restore nothing, fail closed |
| `CORRUPT` | Invalid JSON/envelope/checksum/schema or unreadable persisted input | Preserve evidence and fail closed; a restoration/I/O failure also requires a fresh runtime |

The classification concerns the durable operation, which may be an entry, close,
protection update or account mutation. It is not a claim that every completed
operation necessarily produced a fill. A coherent submitted order without a fill
remains unresolved; it creates neither a position nor PnL during restoration.

Partial entry restoration requires the actual filled quantity, entry price,
broker position, canonical journal/portfolio/account and protection/OCO records
to agree. An isolated fill cannot supply missing journal fields or protective IDs.
The normal PAPER engine currently emits full entries; partial-entry reconciliation
is verified using an explicit persisted fixture, without extending that engine.
Actual process-exit tests exercise PAPER partial **close** fills.

## Evidence and write ordering

The existing checkpoint format remains version 1/schema 2.0. New PENDING records
include an operation UUID. A sibling `<checkpoint>.evidence.json` contains:

- version, operation UUID, exact PENDING checksum and checkpoint generation;
- observation stage and UTC recording timestamp;
- the captured participant state, preserving original order, execution/fill,
  position, client-order, journal and protective identities and timestamps;
- SHA-256 over canonical JSON, rejecting nonfinite numbers.

The exclusive OS writer lease and reentrant mutation lock cover both files.
Each evidence replacement uses the same fsync/atomic-replace primitive as the
checkpoint. There is one bounded sidecar, replaced by the next operation after
successful completion; unresolved evidence cannot be overwritten by the failed
runtime. Timestamps provide traceability; decisions use identities, phase ordering,
generation, checksums and participant consistency, never elapsed-time heuristics.

Outer operation ordering:

1. Validate the baseline; generate operation identity and PENDING checksum.
2. Persist PREPARED evidence, then PENDING.
3. Persist STARTED **before** entering the operation body.
4. Before each nested participant mutation, persist STARTED to invalidate any
   earlier observation; after its return, persist OBSERVED with all participants.
   Observations can be inconsistent and do not themselves grant recovery authority.
5. After the outer operation returns, validate its complete state and persist
   COMPLETED evidence before writing the existing COMMITTED checkpoint.

The PAPER connector participates in this fence for submit/modify/cancel/partial
close/full close; the real broker implementation is unchanged. A crash inside a
later broker close therefore cannot cause an older open-position observation to
be restored. Ordinary startup still refuses PENDING; reconciliation is explicit.
Orphan evidence (including temporary evidence) prevents clean startup or manual
snapshot overwrite when the main checkpoint is absent.

## Consistency and restoration

Validation uses the existing execution-state and account/portfolio validators,
plus reconciliation-specific checks:

- exact operation/generation/PENDING-checksum linkage;
- immutable historical fills, order identities and client-order index mappings;
- unique fill IDs, entry-order/position bijection and portfolio/broker bijection;
- journal/portfolio identity, status, quantity and cumulative PnL consistency;
- entry fill/order/journal/broker symbol, direction, price and quantity agreement;
- partial-fill quantity conservation, identity, side and symbol agreement;
- matching exit prices for closed broker/journal/portfolio positions;
- terminal journal, portfolio, PAPER position, protection and OCO records cannot
  disappear, change, or become open again;
- account financial baselines, daily loss capacity, drawdown and risk blocks;
- exact active protection/OCO identities, quantities, stop and target records.

Reconciliation reuses full-state restoration. It replaces saved collections and
restores cumulative account baselines; it never calls broker execution, journal
open/close or accounting callbacks. After restoration it compares the actual
participant state with the evidence before installing COMMITTED. Only the capture
timestamp is excluded from this comparison. Existing current or persisted risk
blocks cannot be removed. A successfully resolved runtime retains its writer lease
and durable mutation protection; LIVE is never enabled.

Partial restoration is a blocked view of the last proven state, not a claim that
the unresolved remainder completed. No fallback to an earlier coherent observation
is allowed when the latest evidence is inconsistent or another step has started.

## Operator procedure

Use a fresh canonical PAPER runtime with the same account/risk/journal configuration.
Keep monitors and request processing offline while invoking:

```python
report = recovery.reconcile_pending_from(file_path=checkpoint_path)
```

Here `recovery` is the runtime's `StateRecoveryServiceV2`, attached to its canonical
`ExecutionStateStoreV2`. Inspect `status`, `resolved`, `restored`, `reason`,
`operation_id`, `pending_checksum`, `generation` and `idempotent` in the report.
Only a resolved result permits normal runtime startup. An unresolved result must
remain offline; preserve the checkpoint, evidence and any temporary files.

Do not reuse a runtime that already failed startup or partially failed restoration.
Dispose of that runtime/release its durability lease, then create a fresh one for
an explicit retry. This procedure does not clear structural/account risk blocks.

Repeated reconciliation with identical evidence and operational state returns the
same outcome with `idempotent=True`. Changed evidence/state requires a fresh runtime;
an older operation cannot be replayed over subsequent valid operations.

## Crash during reconciliation

PENDING and its evidence remain authoritative throughout restoration. Only after
exact restoration does an atomic write install COMMITTED with a reconciliation
receipt containing the source operation, generation and PENDING checksum.

- Crash during collection restoration or before commit: a fresh runtime reconstructs
  from the same evidence, without replaying accounting/execution callbacks.
- Crash after flushing the reconciliation temporary checkpoint but before replace:
  resume only if its bytes exactly match the candidate independently derived from
  PENDING and its evidence. Other temporary content remains ambiguous and untouched.
- Crash after replace: the committed receipt and ordinary recovery establish the
  completed result; subsequent reconciliation is idempotent.
- Unresolved partial results never install a committed checkpoint.

## Tests and verification

`backend/tests/test_pending_operation_reconciliation_v2.py` covers the requested
matrix A–K with real child processes using `os._exit(23)`, plus explicit malformed
or contradictory persisted fixtures. Full participant equality verifies IDs,
fills, journal, portfolio, account/PnL and all active/terminal protection/OCO records.
Forbidden-call spies verify restoration does not replay execution/accounting.

Additional checks cover legacy PENDING refusal, an operation interrupted inside a
later close, structural blocks, orphan evidence, competing writers, LIVE refusal,
repeated corrupt/ambiguous outcomes, partial-entry evidence and evidence fsync failure.

The consolidated run uses the same 40 test files listed in the **TESTS EXECUTED**
section of `durable_crash_recovery_v2.md`, plus these three exact files:

- `backend/tests/test_pending_operation_reconciliation_v2.py`
- `backend/tests/test_paper_broker_partial_close_v2.py`
- `backend/tests/test_broker_connector_v2.py`

Initial implementation command (historical; superseded by the final review below):

```powershell
@'
import os, re, tempfile
from pathlib import Path
import pytest
from backend.tests.test_partial_take_profit_policy_authority_v2 import UNRELATED_REQUIRED_ENV
os.environ.update(UNRELATED_REQUIRED_ENV)
os.environ.update(ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS='20', ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION='0.5')
paths = sorted(set(re.findall(r'backend/tests/test_[a-z0-9_]+\.py', Path('docs/architecture/durable_crash_recovery_v2.md').read_text(encoding='utf-8'))))
paths += ['backend/tests/test_pending_operation_reconciliation_v2.py', 'backend/tests/test_paper_broker_partial_close_v2.py', 'backend/tests/test_broker_connector_v2.py']
raise SystemExit(pytest.main(paths + ['-q', '-p', 'no:cacheprovider', '--tb=short', '--basetemp', tempfile.mkdtemp(prefix='arms-phase08-')]))
'@ | python -
```

Settings above are synthetic test-process inputs; no secrets/configuration files
are read or changed for this setup. A unique test temporary directory avoids the
pre-existing pytest directory owned by a different Windows user.

Initial implementation verification results (superseded by the final consolidated run below):

- Focused reconciliation suite: **44 passed**, no skips (15.74 seconds).
- Earlier four-file recovery/reconciliation run: **115 passed** (27.44 seconds),
  before the last two additional reconciliation tests.
- Final 43-file consolidated run: **544 passed, 3 failed** (39.38 seconds).
  All three failures were `PermissionError` when existing app E2E tests attempted
  to persist `data/risk_events.json` in the read-only repository location.
- Exact retry of those three tests in an isolated temporary working directory:
  **3 passed** (1.62 seconds). No production data or existing E2E tests were changed.
- Thus all **547 distinct selected tests** were verified successfully, across the
  consolidated run and the isolated retry. The installed Starlette/httpx deprecation
  warning remains; no dependency change was made.
- Final diff review: `git diff --check` passed; new Python files parse successfully
  and all new files pass whitespace inspection. Branch and HEAD remain the expected
  values above. Five existing files changed and three new files were added; no
  unrelated files, real broker, secrets, root instructions or master documents changed.

Exact isolated retry command (same synthetic settings):

```powershell
@'
import os, sys, tempfile
from pathlib import Path
import pytest
from backend.tests.test_partial_take_profit_policy_authority_v2 import UNRELATED_REQUIRED_ENV
root = Path.cwd()
os.environ.update(UNRELATED_REQUIRED_ENV)
os.environ.update(ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS='20', ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION='0.5')
sys.path.insert(0, str(root))
os.chdir(tempfile.mkdtemp(prefix='arms-phase08-e2e-'))
paths = [str(root / 'backend/tests/test_live_position_monitor_realtime_e2e_v2.py'), str(root / 'backend/tests/test_live_position_monitor_trade_learning_e2e_v2.py')]
raise SystemExit(pytest.main(paths + ['-q', '-p', 'no:cacheprovider', '--tb=short', '--basetemp', tempfile.mkdtemp(prefix='arms-phase08-')]))
'@ | python -
```

The initial default-pytest-temporary-directory attempt also hit Windows ownership
permissions; subsequent runs used fresh directories. During implementation, tests
exposed outdated fault-injection assumptions and test-only module/UTF-8 fixture
loading mistakes, which were corrected before the reported passing runs.

## Files changed

- `backend/services/durable_execution_state_v2.py`: linked evidence and mutation stages.
- `backend/connectors/paper_broker_connector_v2.py`: PAPER mutation participation.
- `backend/services/execution_state_store_v2.py`: register PAPER participant; orphan-evidence guard.
- `backend/services/pending_operation_reconciliation_v2.py`: statuses, evidence validation, restoration and receipts.
- `backend/services/state_recovery_service_v2.py`: explicit reconciliation entry point and orphan detection.
- `backend/tests/test_durable_crash_recovery_v2.py`: adapt fault injection to the additional evidence writes.
- `backend/tests/test_pending_operation_reconciliation_v2.py`: reconciliation regression matrix.
- `docs/architecture/pending_operation_reconciliation_v2.md`: model, operator procedure and validation record.

## Remaining limitations and next step

- Existing Phase 0.7 PENDING records have no operation-bound post-baseline evidence.
  They remain AMBIGUOUS; neither missing fills nor an old baseline proves an outcome.
- A broker-only fill with absent canonical journal/account/protection evidence remains
  AMBIGUOUS. Missing identities, timestamps or accounting fields are never synthesized.
- Partial entry evidence supports the existing single-entry-fill representation;
  unsupported/multiple-entry-fill layouts remain blocked pending independent validation.
- Evidence adds synchronous full-state writes at participant boundaries. Storage cost
  grows with retained history; performance and physical power-loss guarantees were not
  benchmarked. Windows testing demonstrates abrupt process exit, not power failure.
- Checksums detect corruption, not malicious replacement or external rollback of an
  entire consistent checkpoint/evidence pair. This is the existing local storage trust
  boundary; no external broker service is queried.

Next recommended step: independently review the PAPER reconciliation procedure and
fault matrix before any production PAPER rollout. LIVE remains outside this phase.

## Final pre-commit review

The final review found and reproduced a quantity-conservation defect: a CLOSED
position bypassed the remaining-quantity check, allowing a contradictory partial
fill larger than its entry to be classified CONFIRMED_EXECUTED. The failing
regression was demonstrated before correction. Reconciliation now checks that
entry quantity minus partial closes is positive and matches both portfolio and
PAPER quantities for OPEN **and CLOSED** positions. PAPER terminal records retain
the last open quantity; restoration must preserve that representation exactly.

The existing partial-entry regression now also checks inconsistent partial-close
quantities in open and closed positions, evidence preservation, zero restoration,
zero PnL, repeated reconciliation and denial of further execution. The existing
crash tests additionally interrupt before reconstruction and verify the original
PENDING and evidence remain byte-for-byte unchanged. These additions expand the
existing test bodies; the exact original selection still contains 547 tests.

Reconciliation does not write a new PENDING: it retains the original fence until
the complete reconstructed state is atomically committed. The verified windows
are before reconstruction, during reconstruction, before COMMITTED, after fsync
of its temporary file, and after COMMITTED before return. The existing durable
crash-window tests also cover interruption before a new operation's PENDING.

All requested contradiction classes remain blocked: broker fill without canonical
journal, journal/active position without demonstrated broker fill, inconsistent
partial quantities, unrelated generations and incompatible/checksum-corrupt evidence.
No contradictory case is promoted to CONFIRMED_EXECUTED. Historical PENDING without
sufficient linked evidence remains AMBIGUOUS; repeated restoration is idempotent.

The final test process uses a fresh writable **working directory as well as a
fresh pytest temporary directory**. Absolute test/source paths and the repository
import path preserve the same code and 43-file selection, while relative app data
such as `data/risk_events.json` is written only inside that isolated directory.
No existing E2E test, production data, risk policy or filesystem permissions were
changed to work around the environment. No test was removed, skipped or separately
retried as part of the final consolidated result.

Exact final command from `C:/Development/ARMS-AI` (PowerShell):

```powershell
@'
import os, sys, re, tempfile
from pathlib import Path
import pytest
root = Path.cwd()
sys.path.insert(0, str(root))
from backend.tests.test_partial_take_profit_policy_authority_v2 import UNRELATED_REQUIRED_ENV
os.environ.update(UNRELATED_REQUIRED_ENV)
os.environ.update(ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS='20', ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION='0.5')
paths = sorted(set(re.findall(r'backend/tests/test_[a-z0-9_]+\.py', (root / 'docs/architecture/durable_crash_recovery_v2.md').read_text(encoding='utf-8'))))
paths += ['backend/tests/test_pending_operation_reconciliation_v2.py', 'backend/tests/test_paper_broker_partial_close_v2.py', 'backend/tests/test_broker_connector_v2.py']
sandbox = Path(tempfile.mkdtemp(prefix='arms-phase08-final-'))
os.chdir(sandbox)
class Audit:
    def pytest_collection_finish(self, session):
        assert len(session.items) == 547, len(session.items)
        print('\nVerified collection: 547 tests in 43 files', flush=True)
print('Isolated writable cwd:', sandbox, flush=True)
print('Source root:', root, flush=True)
raise SystemExit(pytest.main([str(root / p) for p in paths] + ['-q', '-p', 'no:cacheprovider', '--tb=short', '--basetemp', str(sandbox / 'pytest'), '--junitxml', str(sandbox / 'results.xml')], plugins=[Audit()]))
'@ | python -
```

The final commit scope remains exactly the eight files listed above. Root
`AGENTS.md` and `docs/master/` are pre-existing untracked files, are not staged,
and are explicitly excluded from the future Phase 0.8 commit. The Git index is
empty; no commit or push has been performed. LIVE is not enabled, the real broker
and secrets are untouched, and existing read-side endpoint changes remain intact.

**FINAL CONSOLIDATED TEST RESULT: 547 passed, 0 failed, 0 errors, 0 skipped** in
one invocation, **40.65 seconds**, after the quantity-conservation correction.
JUnit confirms 547 unique test cases. One existing Starlette/httpx deprecation
warning remains. Results: `C:/Users/Thecrazyboss/AppData/Local/Temp/arms-phase08-final-5sh3zaug/results.xml`.
The earlier combined/retry implementation results are superseded by this run.

`git diff --check` passed. HEAD remains
`8dac83f666f4f0e126bd9d2c8d933200920e73de` on `refactor/backend-architecture`.
**READY FOR COMMIT: YES**, within the documented PAPER scope. No commit or push.
