# Sprint 16A-R5: false-return investigation and bounded diagnostic design

Status: **DESIGN ONLY. No R5 implementation, installation, preparation for activation, or native execution.** Baseline is `c24f225cf3984f020e49979b10077a4739bb588c` on `refactor/backend-architecture`. R3, the committed R4 component/verifier, both exporters, and historical admission rules remain unchanged. Do not replace `AddTicks(1)` with `AddSeconds(1)`.

## Established evidence and recovery

`NATIVE_OBSERVATION`: R4 prepared run `1431fd7d-3672-4898-81a2-b4ad90298dc2`, component probe UUID `a9886985-ccfd-4f3c-bdb8-fd8e96d3f0d1`. The committed verifier accepts its 13 records, four calls, 20,360 JSONL bytes and 439-byte seal. JSONL SHA-256 is `ac8d758d1087223dac7376272f8b36a0bd568ada171550f432a4ea256d79179b`; seal SHA-256 is `202ea5f17140248ca275f3cf503eb15bd736994f98f29f4e3f9b1ccaa20dc5e7`. Writer-closed and diagnostic-complete flags are true. Outcome is **FAIL** for the +1-second candidate, not a failed evidence-integrity check.

Both fresh Bars-based iterators first received `2026-09-14T00:00:00.0000000Z`, returned true, and reported UTC bounds `2026-09-13T22:00:00Z` through `2026-09-14T21:00:00Z`. A's second query was `2026-09-14T21:00:00.0000001Z`; B's was `2026-09-14T21:00:01.0000000Z`. Both returned false with no exception or guard failure. All queries were Utc and included end timestamps. False-result bounds were not read. Both sequences shared the same stable 4,503-row snapshot and verified configuration. Native collection provenance rests on the operator report; the seal/verifier does not independently attest provenance.

R2's preserved capture contains only `historical-diagnostic.jsonl`, SHA-256 `b7428c3c378cced5a2b328c44671fcd6100d4c5eab0033a169639b6da0b2678b`. It terminates at `FAILED_CALENDAR_ADVANCE_FALSE`, before the exporter reaches its bar-reading/export loop. R4's capture contains only its diagnostic JSONL and seal. Neither capture contains a timestamp ledger or exported Bars payload.

## 1. Snapshot temporal coverage

| Requested finding | Supported result |
| --- | --- |
| First returned bar time / Kind | UNKNOWN / UNKNOWN; not recorded |
| Last returned bar time / Kind | UNKNOWN / UNKNOWN; not recorded |
| Data after September 14 21:00Z | UNKNOWN |
| September 15, 16, 17, 18, and 20/21 coverage | UNKNOWN for each date/session |

R4 requested September 16 through September 21 with Unspecified request dates. This records the requested range, not the actual returned endpoints or gaps. Its snapshot SHA-256 `501d963a14c1a2b59713994a3ef07e65f423b5246205d07d488e516548c771c6` commits to timestamp representations and OHLCV, but the fingerprint input was not persisted. It cannot supply the missing endpoints. The same row count in R2 and R4 does not establish the same snapshot.

The original initial query precedes the requested range. This makes coverage a justified question, but is not proof that the native snapshot starts on September 16. First-call success already prevents a blanket assertion that the requested date range alone limits every calculation. Synthetic fixtures, current chart data, newly inspected repository data, and unrelated exports cannot fill this historical snapshot evidence gap.

## 2. Public contract and installed metadata

`DOCUMENTED_PUBLIC_CONTRACT`: [GetNextSession](https://docs.ninjatrader.com/ninjascript/getnextsession) selects relative to the supplied DateTime and returns a Boolean indicating successful calculation. Its inclusion parameter controls end-timestamp membership. The examples reuse a Bars-derived iterator with the current bar time when a session starts. They do not enumerate exhaustive false predicates, maintenance-gap behavior, comparison precision, or guarantee arbitrary calendar traversal. There is no documented rule that repeatedly passing an unchanged query advances one session.

`DOCUMENTED_PUBLIC_CONTRACT`: [SessionIterator](https://docs.ninjatrader.com/ninjascript/sessioniterator) associates session information with a Bars series and describes historical queries through a stored iterator. It does not explicitly choose between unrestricted template traversal and sessions constrained by available Bars. **Domain classification: C, contract does not establish A or B.**

The [ActualSessionEnd](https://docs.ninjatrader.com/ninjascript/actualsessionend) page describes conversion to the configured user timezone; overview wording also refers to PC-local time. That wording does not establish automatic DateTime.Kind conversion. Keep the observed UTC query domain and preserve raw returned Kinds. No relabeling or timezone-conversion repair follows from this review. These are current NT8 public pages, not a pinned 8.1.8.2 implementation specification.

`INSTALLED_BUILTIN_USAGE_EVIDENCE` / metadata: the installed Core assembly is version 8.1.8.2, SHA-256 `89d30ce74dfb21c26c0819db1f5979799b152d522bbfbc436a3b2cfb495b9408`. Fresh reflection-only inspection confirms public constructors for `Bars` and `TradingHours`, and `Boolean GetNextSession(DateTime timeLocal, Boolean includesEndTimeStamp)`. Installed Core XML documents the Bars constructor and relative-date semantics; it does not resolve the domain question. The TradingHours constructor is demonstrated by installed callers, not established by the reviewed public Bars-constructor documentation.

Exposed GetNextSession IL remains `20000000002a` (constant false), and constructor bodies only call a base constructor. These exposed bodies cannot explain the observed native true results. No method/constructor was invoked to infer real native behavior. The existing R3 metadata harness loaded no NinjaTrader assembly for execution. Metadata fields and these bodies cannot establish the actual runtime's false-return predicate.

## 3. Installed callers reviewed in context

All paths below are relative to installed `NinjaTrader 8/bin/Custom`. Hashes and call-site inventories are preserved privately for this review. These are observations of caller code, not demonstrations that a returned false is an error in that caller.

| Component | Construction | First/recurrent query | Inclusion and ActualSessionEnd use | Reuse / Bars progression |
| --- | --- | --- | --- | --- |
| `BarsTypes/@MinuteBarsType.cs`: 43-57, 84-110 | Lazy `new SessionIterator(bars)`, line 45 | Incoming `time` after IsNewSession; carry-over branch can then query end +1 second | `isBar` for both; end read to cap or carry computed timestamps; Boolean ignored | Reused across OnDataPoint events; AddBar/UpdateBar changes Bars across events. No Bars update between the two calls within TimeToBarTime |
| `BarsTypes/@SecondBarsType.cs`: 26-36, 62-88 | Lazy Bars iterator, line 28 | Same two patterns with second-based rounding | `isBar`; end +1 second in carry-over branch; Boolean ignored | Same mutable incoming-data lifecycle; no intervening Bars update within helper |
| `BarsTypes/@HeikenAshiBarsType.cs`: 110, 434-459, 473-498 | Lazy Bars iterator | Incoming `time`, then conditional end +1 second in minute/second helpers | `isBar`; end used to calculate carry-over; Boolean ignored | Reused while OnDataPoint builds Bars; helper calls can be back-to-back without a Bars update |
| `BarsTypes/@KagiBarsType.cs`: 129, 383-408, 422-447 | Lazy Bars iterator | Incoming `time`, then conditional end +1 second in minute/second helpers | `isBar`; end used for carry-over; Boolean ignored | Same relevant helper pattern; other base-period branches have different queries |
| `BarsTypes/@LineBreakBarsType.cs`: 81, 470-495, 509-534 | Lazy Bars iterator | Incoming `time`, then conditional end +1 second in minute/second helpers | `isBar`; end used for carry-over; Boolean ignored | Same relevant helper pattern; other branches use input or calculated timestamps |
| `Indicators/@Pivots.cs`: 84, 168, 215-230 | Stored `new SessionIterator(Bars)` at DataLoaded | `Times[0][0]` when later than cached session end | `true`; end becomes a cache and is shifted -1 second for trading-date conversion, never +offset as the next query | Reused as OnBarUpdate advances through chart bars; no static snapshot traversal loop |
| `MarketAnalyzerColumns/@ChartNetChange.cs`: 49-84, 110-128 | `new SessionIterator(TradingHoursInstance)` | Startup may query a computed trading-day begin +1 second, after other session helpers; later `now` | `false`; no previous-session-end advancement | Reused; constructed without Bars. Clock/render progresses; IsInSession/IsNewSession also act on this iterator |
| `MarketAnalyzerColumns/@DaysUntilRollover.cs`: 34-54 | Lazy `new SessionIterator(Instrument.MasterInstrument.TradingHours)` | `now` when beyond cached trading-day end | `false`; tests ActualTradingDayEndLocal, does not form end +offset query | Reused by periodic caller; no Bars input required (`IsDataSeriesRequired=false`). This timer is observed code, not an R5 design feature |

The five carry-over helpers enter the end-plus-second branch only with reset-on-new-trading-day false and existing bars. R4 requests reset=true. They also consult IsNewSession first and ignore GetNextSession's Boolean. Consequently, neither mandatory external Bars advancement nor guaranteed successful end-plus-second traversal is established by those examples. The Bars object need not advance between helper calls, but its broader ingestion context differs from R4's completed repository snapshot.

`INFERENCE`: repeated end-plus-offset queries have installed precedent; it is incorrect to call that convention inherently invalid. R4 disproves its sufficiency for this snapshot/context. Current-bar timestamps and TradingHours-based construction are useful experimental controls, not authorized production replacements.

## 4. Trading-hours expectations

`INSTALLED_BUILTIN_USAGE_EVIDENCE`: the disk template is `CME US Index Futures ETH`, version 5119, `Central Standard Time`, SHA-256 `370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620`. Its weekly sessions open Sunday through Thursday at 17:00 Central and close the following day at 16:00. The only September 2026 exception in this file is September 7, outside the reviewed interval. Windows timezone conversion yields:

| Trading day | Begin UTC | End UTC |
| --- | --- | --- |
| September 14 | September 13 22:00 | September 14 21:00 |
| September 15 | September 14 22:00 | September 15 21:00 |
| September 16 | September 15 22:00 | September 16 21:00 |
| September 17 | September 16 22:00 | September 17 21:00 |
| September 18 | September 17 22:00 | September 18 21:00 |
| September 21 | September 20 22:00 | September 21 21:00 |

`INFERENCE FROM TEMPLATE`: the native first bounds match this schedule exactly. Expected next bounds are **September 14 22:00Z through September 15 21:00Z**. The ordinary daily maintenance interval is 21:00-22:00Z on these dates; Friday close through Sunday reopen is a longer closure. Both failed R4 second queries lie strictly inside Monday's maintenance interval. This establishes query location, **not that GetNextSession must return false there**. R4 records loaded template name/version/timezone but not a full loaded schedule/holiday digest; disk agreement is not proof of complete loaded-template identity.

## 5. Root-cause candidates and limits

| Candidate | Evidence and limitation |
| --- | --- |
| Maintenance-gap query semantics | Both failed queries are in the same gap; a fresh gap query and a next-session interior query were not tested |
| Iterator state / query convention | Both chains repeat the same state transition; fresh next queries could differ from reused ones. Independent A/B objects exclude shared A-to-B state, not each object's internal state |
| Bars snapshot coverage / constructor context | No timestamp coverage was emitted, and queries precede the requested dates; a Bars-covered timestamp and paired TradingHours constructor are missing controls |
| End inclusion semantics | Only true was tested; an exact-end true/false pair is needed if boundary behavior remains material |
| Native runtime or loaded calendar discrepancy | No reliable runtime implementation body or full loaded calendar payload is available; these remain residual candidates |

A simple subsecond increment repair is unsupported: +1 second also failed. No exception, changed fingerprint, reversed bounds, invalid successful Kind, or A/B configuration mismatch explains these false returns. R4 demonstrated two independent initial successes and stable observed inputs, not snapshot coverage, direct-next-session behavior, a false-inclusion result, arbitrary template traversal, or a full coverage algorithm. Root cause remains **UNRESOLVED**; behavioral repair threshold remains **NOT_MET**.

## 6. Proposed R5 diagnostic: five core calls, eight maximum

Proposed new component: **ArmsSessionDomainProbeV1**, design identity only; no corresponding source file exists. Preserve R4 reproducibility. A later implementation and native run require separate review/authorization. No attempt directory, timer, or activation is prepared by this design.

Use one opt-in repository-only request with the R4 target, fixed request dates/policies, UTC/Playback checks and operator gates. No Update subscription, additional series, provider fallback, retry, account API, order/execution API, connection mutation or historical output. All defaults remain disabled. A new snapshot must be fingerprinted and compared with R4: matching hashes support continuity, while a mismatch prohibits attributing cross-run differences solely to query behavior. All causal comparisons below use the same new snapshot within one attempt.

### Coverage measurement before any iterator call

Bound the snapshot to 3-10,002 rows. Read **all returned timestamps**, including first and last, preserving index, seven fractional digits and raw Kind. Record first/last time/Kind, strictly increasing order status, UTC-date buckets, and counts/first/last indices for each template-derived session above and for maintenance/outside-session labels. Use end-labelled Minute/1 membership `(begin, end]`; separately flag exact boundaries and partial first/last rows. Counts demonstrate represented labels, not complete candles, continuity, or certification. Do not infer interior coverage from endpoints alone.

Record the count of actual labels strictly after September 14 21:00Z and per-date/per-session coverage around September 15, 16, 17, 18 and 20/21. No UTC relabeling is allowed; invalid Kind/order makes coverage unresolved and blocks query adjudication. For the covered-data control, choose the lowest source index in `1..Count-2` whose UTC timestamp is strictly inside one of the listed post-first-session intervals. Preserve its exact native timestamp and index; do not manufacture a substitute when absent.

Record loaded TradingHours name/version/timezone plus its bounded session/holiday definition or canonical digest with separately retained canonical input. A digest alone is not sufficient for offline template reconstruction. Verify count, identities and fingerprint again after the matrix. Never serialize account or provider-owned exception text, and do not export OHLCV history. Native Bars.GetTime reads and constructors are separate from the GetNextSession call budget; the row scan and fingerprint passes must also be bounded.

### Core matrix (up to five GetNextSession calls)

All queries have Kind Utc and includeEndTime=true. Persist CALL_BEGIN before every call and CALL_RESULT afterward. Each direct query gets its own fresh Bars-derived iterator, with no preceding IsInSession/IsNewSession/CalculateTradingDay calls.

| ID | Iterator | Query | Purpose |
| --- | --- | --- | --- |
| R0 | Fresh Bars iterator R | `2026-09-14T00:00:00.0000000Z` | Same-run positive anchor; require the established first bounds before R1 |
| R1 | Reuse R once | R0.ActualSessionEnd +1 second | Same-run state-dependent gap control; skip if R0 is false, exceptional or invalid |
| G | Fresh Bars iterator G | `2026-09-14T21:00:01.0000000Z` | Exact same gap query as R1, without prior state |
| N | Fresh Bars iterator N | `2026-09-14T22:00:01.0000000Z` | Strictly inside the template-derived next session, avoiding both boundaries |
| C | Fresh Bars iterator C | Exact observed interior bar timestamp selected above | Positive control inside demonstrated post-first-session snapshot coverage; skip explicitly if absent |

R1 is a control in a separately proposed R5 experiment, not authorization to reapply or rerun the existing R4 probe. A false result terminates that iterator's chain but can be recorded before moving to an independent control. No bounds are read after false. Do not continue R to another date after R1 fails.

### Conditional controls (at most three additional calls)

The predicates must be fixed in the reviewed implementation; no operator-chosen expansion or retry within an attempt.

* **E_TRUE / E_FALSE, two fresh Bars iterators:** only if G is false without exception and N succeeds with valid expected next bounds, compare the exact prior end `2026-09-14T21:00:00.0000000Z` with true and false inclusion. This tests the endpoint separately from the gap. Record native outcome/bounds; do not predetermine false-inclusion success or its bounds.
* **T_NEXT, one fresh TradingHours iterator:** only if measured next-session label count is zero, or N is false while C succeeds with valid bounds. Construct from the **same returned `bars.TradingHours`**, not a second disk lookup, and use N's exact query with true inclusion. The overload is present in installed metadata and built-ins. This is an experimental constructor-context comparison, not an established alternative calendar authority. If loaded template identity cannot be bound, skip as unresolved.

**Hard maximum: eight GetNextSession invocations, at most seven iterator objects, one BarsRequest.** Increment the call counter before invocation so exceptions consume budget. Failed prerequisites reduce the call count and must produce explicit skip reasons; they never enable replacement calls. Count arithmetic is 2 reused-chain +3 direct +2 endpoint +1 template =8. Unconditional probing of every date or offset is not justified.

Candidate `20:59:59Z` is a valid pre-end control but is deferred because R0 already checks that first session. A fresh `21:00:00.0000001Z` query is also deferred: the first diagnostic question is state/gap/coverage, while R4 already refuted +1-second sufficiency. Do not silently add those candidates to the eight-call design. A repeated-identical-query loop, timezone coercion, additional data request, or Bars mutation is outside this design.

### Interpretation, without repair authority

* Valid R0/R1 and G inputs with R1=false/G=true indicate a state-dependent difference for that query on this snapshot. They do not identify the hidden predicate.
* R1=false/G=false/N=true supports a gap-location explanation under tested conditions; E_TRUE/E_FALSE further characterize endpoint inclusion. It is not proof of a general gap contract.
* N=true with **zero measured labels in that next session** is a counterexample to a strict represented-session-only rule for that tested snapshot. It does not prove an unlimited calendar.
* N=false/C=true leaves date/coverage dependence plausible. T_NEXT=true at the same N query isolates a Bars-versus-TradingHours construction difference, not the precise role of missing data.
* N=false/T_NEXT=false does not distinguish a shared calendar/query limitation from other native behavior. C=false, invalid prerequisites, exceptions, changing inputs or unequal context leave the associated comparisons unresolved.
* No combination automatically edits an exporter. A future repair additionally needs native traversal/coverage validation over required history padding, weekdays, maintenance and weekend boundaries while retaining every admission guard.

## 7. Evidence handling and implementation acceptance plan

Use separate R5 record/seal schemas and component version; never reinterpret R4's schema or PASS/FAIL contract. Bound output to 96 records, 16 KiB per record, 256 KiB JSONL and a 4 KiB seal. A canonical loaded-template payload must fit the total limit or fail closed. Record run/probe/snapshot identifiers, installed build identity, request context, coverage measurements, planned/executed/skipped cases, iterator/constructor identity, query/Kind, inclusion, Boolean or sanitized exception, bounds/Kind/validity, guards and monotonic sequence/call counts.

Use a fresh fixed-drive non-reparse private directory; CreateNew output; close/flush the writer before publishing the seal; bind exact bytes/count/SHA-256 and case plan. Interrupted output, limits, callback identity failures, context/fingerprint changes, duplicate or reentrant callbacks and write failures cannot seal a valid comparison. A fully recorded false result may complete a diagnostic but never grants runtime admission. All outputs declare DIAGNOSTIC_ONLY, certification_evidence=false and runtime_admission=false. A hash protects integrity, not native provenance.

The future offline verifier must enforce exact schemas/types, UUIDs, all lifecycle and call pair ordering, independent identities, same-snapshot context, source-index binding, coverage consistency, predicate-controlled optional calls/skips, eight-call limit, UTC representations, nullable false bounds, allowed exceptions and the byte/record/hash seal. It must reject duplicated/missing/unplanned calls and contradictory metadata even with a recomputed seal. Unknown or malformed evidence never becomes a causal conclusion.

Before any implementation is considered complete, synthetic tests must exercise: all result combinations; fresh/reused state differences; no post-first data; noncontiguous date buckets; missing next-session data with later covered data; optional-case predicates; constructor failures; exact seven-digit tick representation; both inclusion values; invalid Kind/order/bounds; late/reentrant callbacks; inline callback then Request failure; directory ownership; output/call limits; missing/corrupt/resealed contradictory evidence; and zero account/order/execution effects. Compile the actual new component against installed 8.1.8.2 and run the relevant safety/calendar/bootstrap regressions. None of those future tests would prove native behavior.

## Validation and proposed scope for this design phase

No new runtime source/tests were necessary to make this investigation and diagnostic plan reviewable. R5 SDK compilation and synthetic execution are **NOT_APPLICABLE_NOT_IMPLEMENTED**. The existing R3 reflection-only and R4 focused suites were freshly run with the recorded repository test-policy environment: **114 passed, zero failures/errors/skips**, including installed 8.1.8.2 compilation of the unchanged R4 source. An offline enumeration of all 64 Boolean scheduling combinations confirmed the design's eight-call/seven-iterator maximum; it does not test a future implementation. The preserved R4 native evidence independently reverified as integrity VERIFIED / candidate FAIL. Template UTC conversions used installed Windows timezone rules. These checks are not a native R5 run.

Exact command/environment, XML/logs, fresh metadata, installed source hashes and template conversions are private under `.arms-dev/sprint16a-r5/investigation-1e2c3431-cfd9-4385-bf24-72731639ea6d/`. They are excluded from commit scope. The sole proposed commit file is this document. No source, installed NinjaScript, template, captured evidence, service, or execution setting was changed; no commit or push is authorized in this phase. Leave the already-run R4 instance alone. Next action is human review of this bounded design before a separately authorized implementation phase.
