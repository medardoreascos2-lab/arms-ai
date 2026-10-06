# R24B Runtime Stability Certification

## Decision

`READY_FOR_FRESH_PAPER_SOAK_RUN`

This decision authorizes only a new, explicitly authorized, supervised PAPER
soak using the pinned Python 3.13.16 environment. It does not authorize LIVE,
external broker execution, indicator Apply, a production deployment, or a
Python 3.14 promotion.

The certification wall soak was bounded to 300.419 seconds. It exercised 16
hours of certified-open synthetic market time, but it was not a 16-hour wall
run. A fresh long PAPER soak remains the next validation step.

## Scope and safety state

- Failed source run: `20261005T062204Z-r23d-r4-f1382474`
- Source failure: fixed 256 MiB L1 stream exhaustion; independent unresolved
  Python 3.14 native access violation (`0xc0000005`, `python314.dll`).
- Operational runtime started during R24B: no.
- NinjaTrader indicator applied during R24B: no.
- Operational PAPER enabled during R24B: no.
- Synthetic authority journal test: yes, in a disposable isolated runtime;
  enable and disable occurred before any subsequent observation, with zero
  fills, positions, trades, or broker calls.
- LIVE execution allowed: false.
- External order authority: false.
- Thresholds retained: confidence 0.80, confluence 0.80, quality 85, RR 2.0,
  risk per trade 0.5%.

## L1 segmented rollover and reader continuity

The NinjaTrader read-only L1 exporter now rotates before a non-terminal write
would consume the terminal reserve. Closed segments are immutable and recorded
in an atomically replaced manifest with monotonically increasing indices,
continuous record sequences, session/provider/instrument/contract identity,
byte counts, and SHA-256 hashes. The final terminal record is sealed into the
last segment.

Explicit terminal classifications are retained:

- `STREAM_CAPACITY_REACHED`
- `PROVIDER_DISCONNECTED`
- `CALLBACK_EXCEPTION`
- `FILE_IO_ERROR`
- `SESSION_TERMINATED`

The reader validates manifest identity, segment order, segment set, sequence
boundaries, sealed sizes and hashes, and immutable file identity. Missing,
duplicate, skipped, mutated, or cross-session/provider segments revoke the
reader. A validated terminal frame revokes immediately even if it becomes
visible just before the exporter's atomic final-manifest swap.

Capacity evidence:

- Evidence: `reports/r24b/20261006T004405Z/l1-capacity-soak.json`
- Python: 3.13.16 x64 standard GIL.
- Total bytes: 272,625,654 (greater than 256 MiB and the prior observed
  268,431,503-byte failure volume).
- Records: 1,073,509; last sequence: 1,073,508.
- Segments: 2 (268,431,357 and 4,194,297 bytes).
- Polls: 4,159.
- Sequence gaps: 0; duplicate records: 0.
- Terminal: `L1_STREAM_TERMINATED:SESSION_TERMINATED`.
- Peak traced Python memory: 977,050 bytes.
- Duration: 411.396 seconds.

The capacity run exposed and fixed a separate Windows short-read assumption in
prefix hashing. The integrity check now loops until it hashes exactly the
requested prefix; it does not weaken overwrite detection.

## Coordinator health and PAPER authority

The Current-PAPER coordinator now inspects L1 immediately after each poll. A
terminal reader produces durable health reason
`L1_STREAM_TERMINATED:<reason>`; other revocations produce
`L1_STREAM_REVOKED:<reason>`. Required L1 loss calls the service health
invalidation path before the coordinator fails closed.

When PAPER is enabled in an isolated runtime and required health is lost, the
runtime transactionally:

1. disables PAPER;
2. records the classified disabled state;
3. commits an authority-transition record with timestamp, run ID, prior/new
   state, reason, initiating path, readiness snapshot, and optional request
   ID/nonce;
4. latches fresh-session authorization as required.

Same-session automatic re-enable is rejected with
`FRESH_AUTHORIZATION_SESSION_REQUIRED`. Tests verify L1 terminal auto-disable,
exact reason/path, two committed audit records, no fills, and no completed
trades.

## Windows supervision and external reporting

`tools/windows_runtime_supervisor_v1.py` creates a Windows Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, immediately assigns the explicit launcher,
and allows backend/frontend descendants to inherit containment. Future
Current-PAPER startup fails closed unless the supervisor supplies the exact run
namespace marker.

The external supervisor atomically persists launcher/child PIDs, raw and hex
Windows exit codes, unexpected-termination and operator-interrupt flags, child
cleanup confirmation, stdout/stderr paths, last health/authority snapshots when
supplied, and the newest eligible WER report path. It never performs shell-wide
process killing.

Controlled evidence:

- Summary: `reports/r24b/20261006T004405Z/crash-injection.json`
- Launcher exit 23 (`0x00000017`): reported; descendants cleaned.
- Backend exit 31 (`0x0000001F`): reported; sibling cleaned.
- Frontend exit 32 (`0x00000020`): reported; sibling cleaned.
- Controller-child exit 33 (`0x00000021`): reported; sibling cleaned.
- All scenarios: unexpected termination true, Job cleanup confirmed, broker
  order calls 0, PAPER false, LIVE false.
- L1 terminal injection is covered separately by the coordinator regression;
  it durably disables PAPER with exact reason and zero execution side effects.

## Fault diagnostics

Certification enabled `PYTHONFAULTHANDLER=1` for supervised children and an
image-scoped user LocalDumps key for `python.exe` under HKCU. The configured
values were `DumpType=2`, `DumpCount=10`, with dump storage under the R24B
evidence directory. Exact prior registry state was recorded in
`localdumps-rollback.json`.

No Python dump directory or eligible WER crash report was created: no Python
process crashed during certification. After testing, the helper restored the
prior registry state and verification confirmed that the previously absent
image-scoped key was absent again. Dump retention is therefore operator-owned
evidence-directory retention; none was generated in this phase.

## Python 3.13.16 environment

- Interpreter: CPython 3.13.16 x64, standard GIL (`Py_GIL_DISABLED=0`).
- Build: MSC v.1944 64 bit (AMD64).
- Isolated environment: repository `.venv`; system Python was not replaced.
- pip: 26.2.1.
- Lock: `backend/requirements-r24b-py313.lock.txt`; all direct and transitive
  packages are exactly pinned and installed binary-only.
- `pip check`: passed.
- Installed set compared with `pip freeze --all`: exact match.
- SQLite: 3.50.4.
- OpenSSL: 3.5.9 (29 Sep 2026).
- App-local VC runtimes: 14.51.36247.0 (`vcruntime140` and `vcruntime140_1`).
- System32 VC runtimes observed: 14.42.34438.0.
- Python 3.14 comparison: not run and not certified. The prior 3.14 native
  access violation remains unresolved because the failed run produced no dump.

## Compatibility regression

Command family: `.venv\Scripts\python.exe -m pytest -q` with the unchanged
explicit commissioning thresholds.

Required-category suite result: **379 passed, 0 failed, 1 pre-existing
Starlette deprecation warning, 52.08 seconds**. Covered Current-PAPER,
controller commands, supervised startup, analysis runtime, L1 exporter/reader,
market adapter, startup catchup, news, risk, entry authority, PAPER/LIVE
isolation, coordinator/lifecycle, shutdown semantics, Job Object supervision,
LocalDumps restore, and the offline soak harness.

Post-review terminal race result: **87 passed, 0 failed, 1 pre-existing
warning, 3.96 seconds** for the complete L1 reader and coordinator files.

Exporter tests compile and run the C# harness against the current SDK. Python
syntax compilation and `git diff --check` passed.

## Bounded runtime soak

Evidence: `reports/r24b/20261006T004405Z/runtime-soak.json`

- Wall duration: 300.419 seconds (configured 300 seconds).
- Synthetic certified-open market time: 16 hours / 960 bars. Closed maintenance
  minutes were skipped by the certified calendar rather than bypassed.
- L1 records: 1,924 across 4 segments; sequence gaps 0.
- L1 terminal: `L1_STREAM_TERMINATED:SESSION_TERMINATED`.
- Decisions: 955; health checks: 960.
- SQLite journal mode: WAL; passive checkpoint result `[0, 688, 688]`.
- Durable synthetic authority transitions: 2.
- Supervised launcher exit: 0; descendant cleanup confirmed.
- Peak traced Python memory: 2,334,488 bytes.
- PAPER orders filled: 0; broker order calls: 0.
- Open positions: 0; closed PAPER trades: 0.
- PAPER enabled at completion: false.
- LIVE/external authority: false.

## Files changed

- L1 producer/consumer: `integrations/ninjatrader/ArmsReadOnlyL1V1.cs`,
  `backend/services/sim_native_l1_authority_v1.py`,
  `backend/market_data/fresh_native_adapter_v1.py`.
- PAPER health/audit/control: `backend/backtesting/current_paper_runtime_v1.py`,
  `backend/backtesting/native_current_paper_coordinator_v1.py`,
  `backend/backtesting/controller_paper_enable_command_v1.py`,
  `backend/api/current_paper_app_v1.py`,
  `tools/start_native_current_paper_v1.py`.
- Supervision/diagnostics/certification tools:
  `tools/windows_runtime_supervisor_v1.py`,
  `tools/windows_fault_diagnostics_v1.py`,
  `tools/r24b_l1_capacity_soak_v1.py`,
  `tools/r24b_runtime_soak_v1.py`,
  `tools/r24b_crash_injection_v1.py`.
- Python lock, regression tests, and this certification document.

Protected pre-existing working-tree changes in `backend/config/accounts.json`
and `frontend/src/lib/api.ts` are excluded from R24B commits.

## Remaining risks and next step

The Python 3.14 access violation has no stack or dump and is not declared fixed.
The Python 3.13 certification did not run for 16 wall-clock hours. Job Object
assignment necessarily follows process creation by a very small interval in the
current Python implementation, although the operational launcher performs
substantial initialization before creating descendants and all controlled
cleanup tests passed.

Next: review the local commits, then explicitly authorize one fresh supervised
long PAPER soak on Python 3.13.16 with LocalDumps re-enabled for that run. Keep
LIVE and external order authority disabled.
