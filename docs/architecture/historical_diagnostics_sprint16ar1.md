# Sprint 16A-R1: persistent historical capture diagnostics

The original capture failure is unresolved. The confirmed defect is an observability gap: the original exporter persisted nothing until a fully validated historical dataset was ready to write. Its two catch paths only called NinjaScript Output. An empty capture directory and an Output window opened afterward do not identify the state, request, callback, or validation that failed.

Baseline: `1d42cc35e8e02353cd53d924835d40476d3fe1b4`, branch `refactor/backend-architecture`. Failed capture: `98107000-26fa-4fba-a0d8-e7b9a90827aa`. The operator reconfirmed enabled capture, September 16–21, 2026, NQ DEC26 Minute/1, ETH and UTC. No historical dataset, seal or diagnostic exists in that capture directory. It remains untouched. Installed authored historical source still matches original Sprint 16A, plus its generated wrapper; the new implementation has not been installed.

## Original execution path

| State/event | Original implementation and conditions |
| --- | --- |
| SetDefaults | Sets CaptureEnabled=false and all three string properties empty; no request or filesystem access. |
| Configure | No branch. No record of effective properties or directory access. |
| DataLoaded | Enters lock. Returns silently if disabled, already attempted, or terminated. Sets attempted=true before validation. Checks UTC/no playback, parses both dates, checks year/order/range, validates existing local empty directory, resolves and checks exact instrument, creates and parameterizes BarsRequest, calls Request once. |
| Historical | No action or retry. |
| Transition | No action or retry. |
| Realtime | No action or retry. |
| Callback | Independently enters lock; returns for termination or wrong request reference. Validates error, source, request/bars identity, calendar, count, native time kinds and OHLCV. Only then writes history and seal. A caught failure only prints a generic message. |
| Terminated | Marks terminated and disposes the retained request. No persistent stage record. |

CaptureEnabled is evaluated at DataLoaded. OutputDirectory and date properties are evaluated inside that guarded attempt. The original header reads the date properties again at callback time. The original attempted flag means an attempt began, not that Request was invoked or that a capture completed. A pre-request failure consumes it and cannot retry during Historical/Realtime or a duplicate DataLoaded callback.

NinjaTrader documents Configure after Apply/OK, DataLoaded after series loading, followed by Historical, Transition and Realtime. Its lifecycle documentation distinguishes configured objects from temporary UI instances and describes cloning. Adding an indicator to an already-loaded chart is not evidence that its new configured object skips DataLoaded. The failed object's actual lifecycle was not recorded. Sources: [OnStateChange](https://docs.ninjatrader.com/ninjascript/onstatechange), [NinjaScript lifecycle](https://docs.ninjatrader.com/ninjascript/understanding_the_lifecycle_of).

## BarsRequest contract audit

Installed SDK 8.1.8.2 metadata and XML match `BarsRequest(Instrument, DateTime, DateTime)` and `Request(Action<BarsRequest, ErrorCode, string>)`. The source requests NQ DEC26, Minute/1 Last, CME US Index Futures ETH, Repository lookup, DoNotMerge, reset at session boundary, and no split/dividend adjustment. It retains the request in an instance field until completion, failure or termination. It does not subscribe to Update or dispose immediately after Request returns.

The documented date overload normalizes to daily local boundaries and requests whole trading days. Under the required application UTC setting, these are UTC date inputs; they do not promise 1440 rows per calendar date. The callback handles errors and the final bar may be forming. The original first/last exclusions remain. A realtime Update subscription is optional for realtime updates and is deliberately absent here. Source: [BarsRequest](https://docs.ninjatrader.com/ninjascript/barsrequest).

Repository lookup selects locally stored data; DoNotMerge requests the named contract without rollover merging. Neither setting establishes provider attribution or guarantees cached coverage. The component makes no provider connection or download request. Missing repository coverage must not be replaced with synthetic bars. An empty result and an error result are distinct tested failure paths; which path the failed native attempt took is unknown.

The installed assembly exposes only a one-byte `ret` body for Request during reflection-only inspection. This metadata surface cannot establish the actual native scheduler, connection prerequisites, empty-cache result or callback dispatch. No native execution was performed to fill that gap. In particular, a connected provider requirement for this specific repository request is **not independently established**. The official sample's connection check concerns realtime subscription. No reviewed contract requires a chart dispatcher for this non-UI callback; the exporter accesses no UI object and serializes its mutable state with a lock. Inline and later worker-thread callbacks pass the offline harness, which does not prove native scheduling behavior.

## R1 change and diagnostic contract

Configure now opens an exclusive, fixed-name `historical-diagnostic.jsonl` in the already existing, empty, fixed-drive, non-reparse output directory. It never creates a missing output directory or writes from SetDefaults. Capture remains opt-in. If Configure saw disabled defaults, DataLoaded can initialize after effective properties are supplied. The request remains at DataLoaded, after the probe has flushed.

The marker contains `arms.nt.historical-diagnostic.v1`, `classification=DIAGNOSTIC_ONLY`, `certification_evidence=false`, and `runtime_admission=false`. It is neither a historical header nor a seal. It records an instance UUID, consecutive sequence, lifecycle state, stage, capture flag, safe normalized dates, property-match flag, directory SHA-256 identity, request invocation/completion/failure flags, returned row count, source index, native time kind, bounded SDK error enum and allowlisted exception category. No exception Message/StackTrace, provider message, account, credential, connection name or literal filesystem path is emitted.

At most 48 records can be written. Each lifecycle state is recorded at most once; there is no per-bar trace loop. File creation uses CreateNew, FileShare.Read, WriteThrough and AutoFlush. The fixed name prevents concurrent attempts from claiming the same empty directory. Serialization requires the directory to contain only the owned diagnostic file before history is written. Unexpected entries fail closed and remain untouched.

Successful stages include INSTANCE_STARTED, CONFIG_VALIDATED, REQUEST_CREATED, REQUEST_SUBMITTING, REQUEST_SUBMITTED, CALLBACK_ENTERED, ROWS_RECEIVED, SERIALIZATION_STARTED, HISTORY_WRITE_STARTED and SEAL_WRITTEN. Failures include the exact guard stage, such as FAILED_CONFIG_DATE_PARSE, FAILED_REQUEST_INVOKE, FAILED_ROW_COUNT or FAILED_CALENDAR_BEGIN_UTC_KIND.

`CONFIG_VALIDATED` means date/property syntax and private directory probe passed; timezone, playback and instrument checks follow at DataLoaded. `request_invoked` means invocation was attempted; `REQUEST_SUBMITTED` means Request returned without throwing. Neither proves callback completion. An inline callback can precede REQUEST_SUBMITTED, including an inline failure: inspect the failure flag and FAILED stage, not just the final record. The distinct completion flag changes only after the closed history and seal have been written. If subsequent diagnostic I/O fails, the actual history/seal must still undergo independent certification; a diagnostic is never admission evidence.

Effective properties are frozen at first enabled attempt and checked again before request and callback. A failed attempt remains latched. Duplicate state changes and callbacks cannot submit again or write another dataset. Termination before completion records a failure and disposes once. A UI clone cannot write or dispose its owner's resources. A new configured instance/reload requires a fresh empty directory; copying an already-owned instance does not rearm it.

Limits: no writable validated directory means there can be no persistent marker there; fixed safe Print is the fallback. Disabled or never-configured instances intentionally create no file. A submitted request with no callback remains pending, not successful; no automatic retry, timeout claim or new capture is introduced. Power loss or storage failure can truncate even a flushed diagnostic; an incomplete final JSON line is not proof of completion.

The offline certifier accepts only the two explicit reviewed authored hashes (original 16A and R1) and records the actual selected hash. Unknown source bytes are rejected. The historical schema, validation, calendar, timing thresholds, bootstrap authority and runtime admission remain unchanged. Diagnostics are rejected as certification input.

## Validation and preservation

See `backend/tests/historical_diagnostics_sprint16ar1.json` for exact source pins, test results, compiled call allowlist and proposed scope. The actual exporter compiles both against installed SDK assemblies and against offline synthetic doubles. The doubles have no account or order APIs. Tests exercise success, inline/asynchronous completion, empty/error callbacks, constructor/request exceptions, native time-kind rejection, unavailable Print, property ordering/mutation, disabled defaults, termination, duplicate states/callbacks, UI clone ownership, reload isolation, unexpected directory entries and diagnostic rejection by the certifier. Synthetic test bars are never native capture evidence.

The first harness run exposed a test-reader sharing-mode bug; its FileStream now permits reading the still-open diagnostic writer. No exporter restriction was relaxed. The focused suite and subsequent regressions passed after this correction. Runtime probes and preservation checks are recorded separately in `.arms-dev/sprint16a-r1/`.

The required healthy LIVE_TAIL/HTTP-200 assertion cannot be made at completion. Independent reads found the original backend/frontend PIDs absent and ports unreachable. The canonical exporter ended at sequence 1276 with TERMINATED at `2026-09-21T18:21:51.3423809Z`. An existing shutdown-result record reports WRITER_CLOSED, DISCONNECTED, and both owned services stopped. This task issued no shutdown, restart or NinjaTrader operation. The old PASS/HTTP-200 fields in that shutdown record are historical startup observations, not current health.

Production exporter source and installed authored/wrapper compatibility remain unchanged. All 971 preserved files, 109 unrelated files and 16 preservation manifests retain their baseline hashes. No files are staged or committed. No execution authority is enabled.

## Human gate

R1 is offline validated instrumentation, not a diagnosed or successful native capture. Only ArmsHistoricalBootstrapV1 will need replacement/recompilation in a separately authorized installation step; the production exporter must not be replaced. No new directory, operator allowance, watcher or capture has been armed. First review the observed production shutdown. A future repeat requires the reviewed historical build, compatibility verification, a fresh isolated directory and an explicit operator activation gate. Do not reuse the failed capture directory or treat its absence of artifacts as success.
