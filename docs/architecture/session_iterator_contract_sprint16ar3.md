# Sprint 16A-R3: GetNextSession boundary contract review

Baseline: `311f1e57b292c1105142a4508ebda0efc78b5ca3`, NinjaTrader SDK 8.1.8.2.

The immediate R2 failure is proven. The underlying native false-return condition is not. No exporter, calendar admission, source pin, or runtime behavior changes in R3. The smallest supported **candidate for a future comparison** is a one-second increment on the same iterator; it is not a proven repair.

## Native evidence and its limits

Capture `f3cf00a6-475f-4c75-8d06-9a6ec245cc24` contains 18 contiguous diagnostic rows, SHA-256 `b7428c3c378cced5a2b328c44671fcd6100d4c5eab0033a169639b6da0b2678b`. Callback error is NoError and returned_rows is 4503. There is no historical artifact or seal. These are reported rows, not validated complete candles.

| Native call | Query (Utc; includeEndTime=true) | Result | Bounds |
| --- | --- | --- | --- |
| Iteration 0 | 2026-09-14T00:00:00.0000000Z | true | 2026-09-13T22:00:00.0000000Z to 2026-09-14T21:00:00.0000000Z, both Utc |
| Iteration 1 | 2026-09-14T21:00:00.0000001Z | false | Not read; current bounds explicitly cleared |

The false return triggers the exporter's own InvalidOperationException and fixed diagnostic message `GetNextSession returned false.` It is not an exception thrown by the native call. No returned repeated/reversed bounds, invalid-Kind guard failure, or native bounds-read exception was observed. Calendar coverage remains incomplete and capture correctly rejects it.

## Installed implementation review

The reviewed Core assembly has SHA-256 `89d30ce74dfb21c26c0819db1f5979799b152d522bbfbc436a3b2cfb495b9408`, version 8.1.8.2, MVID `71909c1c-c63e-459a-b939-8bf53274b526`. A reflection-only inventory of installed NinjaTrader assemblies locates SessionIterator and TradingHours in Core. The installed source search finds consumers, not SessionIterator's implementation source.

The public signature is `Boolean GetNextSession(DateTime timeLocal, Boolean includesEndTimeStamp)`. Exposed IL is `20 00 00 00 00 2A`, a constant-zero return. CalculateTradingDay exposes a bare return; IsNewSession and IsInSession also expose constant-zero bodies. SessionIterator constructors expose only a base-constructor call. These bodies cannot explain the real first-call success and populated bounds in R2. They are not reliable evidence of the running implementation. R3 does not infer how the actual runtime replaces, supplies or executes those bodies.

Both Bars and TradingHours constructor overloads are present in the installed public metadata. There is no parameterless advance overload in the reviewed public methods. Private instance field metadata includes lastTimeLocal, lastTradingDay, tradingHours and includesEndTimeStamp. This establishes stored state, but field names cannot prove its update or comparison rules.

Installed XML says ActualSessionBegin/End are converted to the user's configured timezone. It names the query timeLocal without specifying DateTime.Kind coercion or conversion internals. The public [GetNextSession contract](https://docs.ninjatrader.com/ninjascript/getnextsession) documents a boolean success result and end-timestamp inclusion, but not exhaustive false-return predicates or a minimum query increment.

## Installed source evidence: a useful but limited difference

The installed `@MinuteBarsType.cs` (line 107) and `@SecondBarsType.cs` (line 85) reuse their SessionIterator and call it with **ActualSessionEnd.AddSeconds(1)**. HeikenAshi, Kagi and LineBreak sources also contain this pattern. The minute/second examples occur when a computed bar timestamp exceeds the session end in the branch that carries a bar across sessions. They pass `isBar`, and do not check the boolean return there.

This is direct installed-source support for reusing an iterator with a manually advanced query. It refutes the blanket claim that reuse plus manual advancement is inherently invalid. It does **not** establish that the exporter's true-inclusion, repository-Bars calendar traversal will return true at +1 second, nor that +1 tick is rounded internally. R3 records source hashes and call-site line numbers without modifying installed files.

The public [SessionIterator example](https://docs.ninjatrader.com/ninjascript/sessioniterator) likewise reuses an iterator for successive first-bar timestamps. A [2017 NinjaTrader support response](https://forum.ninjatrader.com/forum/ninjatrader-8/indicator-development/95855-i-believe-the-sessioniterator-isinsession-method-has-serious-bugs) describes state-sensitive false returns during repeated queries and suggests separate iterators for that example. That is evidence for a hypothesis, not proof of the 8.1.8.2 branch in this capture. No concurrent users of the historical exporter's private iterator are present in its code.

### Recovered and independently reviewed installed call sites

All rows below are `INSTALLED_BUILTIN_USAGE_EVIDENCE`, not public API guarantees. Identities are relative to the installed `bin/Custom` directory. Full SHA-256 identities and every GetNextSession call-site line are in the private R3 review report. The ten previously recorded bar-type hashes and the template hash still match. A search of installed `@*.cs` sources found no `AddTicks(1)` occurrence; this is a bounded source-search result, not proof that ticks are unsupported.

| Component and relevant lines | Iterator state | Query construction / inclusion | Boundary handling |
| --- | --- | --- | --- |
| BarsTypes/@MinuteBarsType.cs:87,107 | Stored Bars iterator, reused | `time, isBar`; then end +1 second, `isBar` | Carry-over branch when computed timestamp exceeds end |
| BarsTypes/@SecondBarsType.cs:65,85 | Stored Bars iterator, reused | Same pattern | Same carry-over branch |
| BarsTypes/@HeikenAshiBarsType.cs:437,457,476,496 | Stored Bars iterator, reused | `time, isBar`; end +1 second, `isBar` | Minute and second base-period carry-over branches |
| BarsTypes/@KagiBarsType.cs:386,406,425,445 | Stored Bars iterator, reused | Same pattern | Minute and second base-period carry-over branches |
| BarsTypes/@LineBreakBarsType.cs:473,493,512,532 | Stored Bars iterator, reused | Same pattern | Minute and second base-period carry-over branches |
| BarsTypes/@PointAndFigureBarsType.cs:268,530,552 | Stored Bars iterator, reused | Incoming `time, isBar` | Bounds used to align/cap bar timestamps; no end increment |
| BarsTypes/@RangeBarsType.cs:31 | Stored Bars iterator, reused | Incoming `time, isBar` | New-session detection; no end increment |
| BarsTypes/@RenkoBarsType.cs:38,57,105,133 | Stored Bars iterator, reused | Incoming `time, isBar` | New-session paths; no end increment |
| BarsTypes/@TickBarsType.cs:30 | Stored Bars iterator, reused | Incoming `time, isBar` | New-session detection; no end increment |
| BarsTypes/@VolumeBarsType.cs:31 | Stored Bars iterator, reused | Incoming `time, isBar` | New-session detection; no end increment |
| Indicators/@CamarillaPivots.cs:227 | Stored Bars iterator, reused | Incoming `time, true` | Query after cached end; end minus one second used for session-date conversion |
| Indicators/@FibonacciPivots.cs:223 | Stored Bars iterator, reused | Same pattern | Same session-date calculation |
| Indicators/@Pivots.cs:223 | Stored Bars iterator, reused | Same pattern | Same session-date calculation |
| Indicators/@VolumeProfile.cs:84 | Stored Bars iterator, reused | Incoming `time, true` | Query after cached end; end minus one second used for date conversion |
| MarketAnalyzerColumns/@ChartNetChange.cs:84,121 | Stored TradingHours iterator, reused | Trading-day **begin** +1 second, `false`; later `now, false` | Begin-interior selection and subsequent new-session query; not end traversal |
| MarketAnalyzerColumns/@DaysUntilRollover.cs:41 | Lazy stored TradingHours iterator, reused | `now, false` | Query after trading-day end; no end increment |
| Optimizers/@StrategyGenerator.cs:1801,1804,2113,2116 | Stored primary-Bars iterator; emitted code follows same pattern | Current first-bar time, `true` | First session / first bar of subsequent sessions; no end increment |

The five end-plus-second components ignore the boolean at those call sites and use the resulting begin to carry a computed bar timestamp forward. Their carry-over branches require reset-on-new-trading-day to be false with existing bars. ARMS requests reset-on-new-trading-day=true, constructs a separate iterator over returned repository Bars, checks every boolean, and traverses calendar padding outside the requested data dates. Consequently, ARMS differs in more than just the increment even though iterator reuse and manual advancement are shared.

`DOCUMENTED_PUBLIC_CONTRACT`: the reviewed public GetNextSession page specifies success/failure and the inclusion flag but no exhaustive false predicates, comparison precision, or minimum increment. The ActualSessionBegin/End pages and installed XML describe the configured user timezone. The SessionIterator overview also contains less precise PC-local wording; this does not justify changing the observed UTC domain or coercing DateTime.Kind.

`INFERENCE`: **B — ADD_SECONDS_1_STRONGLY_SUPPORTED_NATIVE_CONFIRMATION_REQUIRED**. Option A is not established: one failed +tick query and several +second consumers do not prove a general incompatibility contract or establish causality for this native failure.

The two legacy forum references in this recovered document could not be fetched successfully during resume. Their earlier summaries are retained as prior-session notes only; the resumed decision rests on the re-read installed sources, preserved R2 trace, and current official API pages.

## Boundary and timezone matrix

The locally installed CME US Index Futures ETH template has SHA-256 `370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620`. Its weekly sessions run Sunday 17:00 to Monday 16:00 Central, then Monday through Thursday 17:00 to the next day 16:00. There is no September 14 exception; September's listed partial holiday is September 7. Reading disk XML does not attest the complete template loaded in the native process; R2's actual first bounds independently agree with this boundary.

The Windows TimeZoneInfo probe uses installed rules, not a fixed Chicago offset. For this September date it produces:

| Representation of the same boundary instant | Wall value | Kind | Meaning |
| --- | --- | --- | --- |
| UTC | 2026-09-14 21:00:00 | Utc | Absolute instant |
| Application UTC wall | 2026-09-14 21:00:00 | Unspecified | Wall value interpreted using explicit application UTC domain |
| TradingHours Central wall | 2026-09-14 16:00:00 | Unspecified | Chicago daylight time, UTC-05:00 |
| Actual OS local | 2026-09-14 17:00:00 | Local | Eastern daylight time, UTC-04:00 on this host |

The matrix repeats each representation at exact end, +1 tick, +1 millisecond and +1 second, preserving seven fractional digits. Chicago wall values mislabeled Utc and UTC wall values mislabeled OS Local are explicitly marked inappropriate representations. No such relabeling is proposed for production.

Thus 21:00Z agrees with the Monday 16:00 Central session end; the next ordinary session begins at 22:00Z. The first session begins Sunday September 13 at 22:00Z. Friday September 18 closes at 21:00Z and Sunday September 20 reopens at 22:00Z under this weekly template. These are template/timezone conclusions, not native results for unexecuted queries.

Utc and Unspecified are not interchangeable API contracts merely because application timezone is UTC. Local means the OS timezone here, not the configured application timezone. Internal Kind interpretation remains unobserved. No ToLocalTime/ToUniversalTime or SpecifyKind repair is justified.

## Candidate evaluation and offline execution gate

| Candidate after the successful first call | Query on September 14 | Evidence/status |
| --- | --- | --- |
| Exact prior end | 21:00:00.0000000Z | Inclusion flag is relevant; native result unknown |
| End +1 tick | 21:00:00.0000001Z | Proven false in R2; this is also the next .NET DateTime value |
| End +1 millisecond | 21:00:00.0010000Z | Native result unknown |
| End +1 second | 21:00:01.0000000Z | Installed-source precedent; native result unknown |
| Next value at NinjaTrader's comparison precision | Unknown | Native comparison precision not established |
| Same query on reused iterator | 00:00:00.0000000Z again | No iterator-managed enumeration guarantee found; native result unknown |
| Independent iterator/query | Next session interior | Diagnostic hypothesis only; native result unknown |

.NET DateTime's representational unit is 100 ns. A [NinjaTrader support response about tick data](https://forum.ninjatrader.com/forum/ninjatrader-8/platform-technical-support-aa/94762-huge-chart-difference-between-ninja-7-and-8) describes sub-second data timestamps. Neither that statement nor built-in bar timestamp rounding proves SessionIterator's internal comparison precision. In particular, R3 does not claim that NinjaTrader globally supports only whole seconds.

`session_iterator_contract_harness_sprint16ar3.cs` is a bounded, standalone metadata/timezone harness. It loads vendor assemblies for reflection only, reports assembly identity and method bodies, and enumerates 11 boundary/state scenarios. It never invokes a NinjaTrader constructor or method, starts the application, makes BarsRequests, or accesses accounts. It verifies that no NinjaTrader assembly was loaded for execution. Its native result and bounds fields are **null**, not false or synthetic successes.

The exposed methods do not provide a validated meaningful offline execution host. Executing their constant-false bodies would merely reproduce a stub and contradict the already observed native success. The harness therefore stops at this capability limit. It does not prove that an independently documented standalone native host is impossible; none was established from the available installation and contract. The earlier R1/R2 synthetic fixtures remain useful for guards, loop bounds and admission parity, not native API truth.

## Repair gate and next evidence

`BEHAVIORAL_REPAIR=NOT_YET_JUSTIFIED`. The first candidate to compare is replacing only AddTicks(1) with AddSeconds(1), retaining the same iterator, includeEndTime=true, calendar coverage, monotonicity checks, UTC-kind guards, 64-call limit, and all historical admission/seal rules. Do not apply it merely because installed callers use it.

To resolve the cause, obtain either the version-specific native false-return predicate/precision contract or a separately authorized isolated native comparison. The original candidate matrix above is retained. The minimal experiment below starts with only +tick versus +second; additional precision/state controls are justified only if the initial results need them. No probe was activated or prepared for native installation in R3.

### Minimal native confirmation experiment — design only

Status: `DESIGNED_NOT_IMPLEMENTED_NOT_STARTED`. Proposed component identity: `ArmsSessionBoundaryProbeV1`, separate from both historical and live exporters. This name describes a future implementation, not an existing deployable file.

**Operator/runtime requirements:** separate, non-production Windows/NinjaTrader 8.1.8.2 test environment with the already-populated local NQ DEC26 repository and the reviewed CME US Index Futures ETH template. Application timezone must be UTC; Playback must be absent. No account selection/access, credentials, broker/provider connection changes, database copying from a running production instance, or history download are part of this plan. If isolated repository data are unavailable, stop; provisioning is a separate task. Explicit authorization is required to implement, review, compile, install and activate this probe. No production chart reload, application recompile, backend/frontend restart, or existing exporter replacement is permitted. The operator supplies a new empty private local output directory and enables one opt-in attempt. An existing suitable isolated test chart is required; creating/loading a chart that would request provider data is outside the experiment.

Use one repository-only BarsRequest with the same R2 instrument, Minute/1 Last, DoNotMerge, reset-on-new-trading-day=true, adjustments=false, requested date properties 2026-09-16 through 2026-09-21, and the same instrument/template/application/Playback guards. No Update subscription, retry, provider fallback, account reference, historical serialization, seal, certification bundle, bootstrap handoff, or runtime admission. A callback error, changed property/identity, missing data, or invalid row count ends the attempt. Record actual row count, SDK/template identity and a bounded snapshot fingerprint; do not claim the repository snapshot is identical to R2 merely because 4,503 rows return.

1. **Primary comparison: four native calls.** Create two independent SessionIterator instances over the exact same returned Bars object. On each, call GetNextSession at `2026-09-14T00:00:00.0000000Z` with includeEndTime=true. Require true and identical ordered UTC bounds matching the R2 first session. On each same iterator, make one second call: prior end +1 tick for the control, prior end +1 second for the candidate. No iterator is shared between the two chains, and no IsInSession/IsNewSession call may mutate their state between calls.
2. **Coverage extension: eight additional calls, only after the primary comparison supports the candidate.** Repeat those independent two-call chains using first queries `2026-09-15T00:00:00Z` and `2026-09-18T00:00:00Z`. Check daily maintenance progression and Friday-to-Sunday reopen against the reviewed template, including Sunday-to-Monday trading-day identity. Total for the paired comparisons is at most 12 calls. An early stop must list unexecuted cases explicitly.
3. **Bounded candidate traversal: at most 64 additional calls.** On a fresh private iterator over that snapshot, test +1-second progression for the original calendar padding, `2026-09-14T00:00:00Z` through `2026-09-29T00:00:00Z`. Preserve every existing calendar guard: require true before admitting bounds, ordered UTC bounds, strictly advancing ends, correct trading-day identity and bounded termination. Compare resulting coverage with the reviewed template including maintenance/weekend exclusions. This is diagnostic output only. A failed step ends this traversal without emitting accepted history or a seal.

Limit the entire attempt to one request, 76 iterator calls and 512 diagnostic records. Persist scenario/iterator identity, sequence, query with seven fractional digits and Kind, inclusion flag, boolean or allowlisted exception type, and separately observed bounds/Kind before and after each call. A false-return bound read, if available, must be explicitly marked `STALE_OR_UNDEFINED_NOT_ADMITTED`; a read exception is a separate diagnostic. Stop that chain immediately on false, nonadvancing/reversed bounds or invalid Kind. Controlled continuation to another independent comparison chain cannot convert a failed chain into success. Dispose the request once and preserve diagnostic exception redaction.

**Decision:** +tick=false and +second=true with valid comparable next bounds supports the candidate in that runtime; successful extended traversal is additionally required before proposing the one-line historical repair. Both false, nonmatching first bounds, exceptions, wrong Kind, changed source identity, or incomplete coverage leave the repair gate closed. Both true means the original failure was not reproduced; it does not establish a +tick precision cause. Even a successful candidate does not reveal the native internal false predicate. Any later exporter edit needs separate source review, source-pin/test updates and regression validation, followed by separately authorized historical capture and certification. None of those actions is authorized by this design.

## Validation and preservation

The R3 tests verify metadata limits, no execution loading, preservation of exact timestamps, timezone equivalence, inappropriate relabeling, and distinct bounded candidate sequences. The regression command covers Sprint 16A, R1/R2, 15Z, market data, aggregation, session/calendar and MVP/execution safety. The existing R2 installed-SDK compile test compiles the unchanged historical exporter against the real SDK using a name-only Indicator shim deriving the real IndicatorRenderBase; this is not an in-application compile or native execution. Exact commands, test results and preservation checks live privately under `.arms-dev/sprint16a-r3/resume-20260921/`, including `regression-command.json`, `regression.xml`, `regression.log`, and `final-review.json`. Test output, binaries and runtime evidence are excluded from proposed commit scope.

The initial regression invocation lacked the explicit API policy test environment and stopped during collection. The corrected invocation uses the repository's CERTIFIED_ENV values only in the test subprocess. It does not change production settings. No historical capture, installation, runtime restart, bootstrap handoff, commit or push is authorized or performed.

## Resume audit, 2026-09-21

Repository, branch and HEAD match the requested baseline. There were no staged files or tracked modifications. All three known untracked R3 files were recovered without truncation; the Python file parses and the C# probe compiles in the regression suite. Additional private R3 artifacts include assembly inventory, metadata/timezone output, source/template hashes, XML excerpts, runtime observations, and two regression attempts. The corrected prior attempt had already completed with 1,779 passes and two warnings. The earlier document referenced a nonexistent repository JSON report; the final report is instead kept private as requested.

The resumed 49-module regression exited with code 0: **1,779 passed, zero failures, zero errors, zero skips, two warnings**, in 151.33 seconds. It includes all seven R3 tests, all 23 R2 tests and the installed SDK compile case. The later resume instruction arrived after this process completed; its exit result, full log and completed JUnit XML were inspected, and no duplicate suite was started. The two warnings are the existing Starlette/httpx deprecation and pytest record_property/xunit2 compatibility warning; neither changes the test result.

The R2 diagnostic remains byte-identical to the hash above, with 18 contiguous records and no history or seal. Existing unrelated untracked work, prior private R3 artifacts, the failed capture, and installed source files were hashed before resumed work. Resumed test outputs use a fresh directory under `.arms-dev/sprint16a-r3/resume-20260921/`; prior test outputs were preserved.

Current production health cannot be reported as healthy. Read-only checks found connection refusal at the recorded backend port 18001 and dashboard port 13001, no listeners on those ports, and the prior backend/frontend PIDs absent. The already-existing shutdown-result.json for run `4945a114-fb72-499e-8456-f21699fa93a3` was last written at 20:43:34 UTC and records TimeoutExpired, STARTUP_OR_HEALTH_FAILED, REVOKED, and both owned services stopped. This records the shutdown outcome, not an independently diagnosed cause of that timeout. NinjaTrader itself remains running and was not manipulated. The recovered 20:03:01 UTC profile (sequence 861, LIVE_TAIL, HTTP 200, execution disabled) is historical evidence only, not a current health or safety attestation.

No behavioral repair or NinjaTrader recompile is required by this R3 diff. Repeat historical capture remains gated. The highest-priority R3 next action is obtaining the version-specific false-return contract or separately authorizing the bounded native comparison described above. Restoring production would be a separate task requiring authorization under the explicit no-start/restart instruction; this phase does not attempt it.
