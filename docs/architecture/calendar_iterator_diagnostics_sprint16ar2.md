# Sprint 16A-R2 calendar iterator diagnostics

Baseline: `97c0eb3fa899a7fb47096a48fad76f917df5b91c`. This change instruments the isolated historical exporter only. It does not install native code, repeat capture, change production, or deploy bootstrap.

## Established failure and limits

Capture `06ad4fe2-b417-4424-9acb-4db251b5a6c9` contains twelve contiguous diagnostic records, ending in `FAILED_CALENDAR_ITERATOR_ADVANCE` / `InvalidOperationException`. Its SHA-256 is `3711006a168dc78253c39f1e55662a859ea8c83521dd89e4e4689c3959e53024`. The callback reported NoError and 4,503 returned rows. No history or seal exists. Returned row count is not validated completed-bar count.

R1 used the same stage for a false GetNextSession return and exceptions from that call or the following bounds getters. Its last observed Kind was Utc; this is retained state from a previous successful property read, not the failing query. The trace cannot reconstruct the failing iteration, query or native operation. The original exact cause remains UNKNOWN. No speculative conversion, interval truncation, retry, or acceptance of an incomplete calendar is proposed.

## Exact unchanged traversal

1. Parse request strings with ParseExact, producing Unspecified midnight values. Request September 16 through September 21, 2026 with BarsRequest's date overload, Repository lookup and DoNotMerge.
2. Set request.TradingHours to the named CME US Index Futures ETH template. At callback, verify returned bars and requested template name/version agree, template timezone is Central Standard Time, application timezone is UTC, and the request remains unadjusted NQ DEC26 Minute/1 Last.
3. Construct `new SessionIterator(bars)` from returned Bars. There is no separately supplied TradingHours constructor argument; the Bars owns the verified template.
4. Set calendarFrom to request start minus two days, with Kind explicitly marked Utc: `2026-09-14T00:00:00Z`. Set calendarThrough to request through plus eight days: `2026-09-29T00:00:00Z`. These are unchanged calendar coverage boundaries, wider than the requested bar dates.
5. For count 0 through 63, call `GetNextSession(query, true)` once. A false return still throws and rejects capture. No retry is introduced.
6. Read ActualSessionBegin, then ActualSessionEnd. Require begin < end and end > lastEnd. If begin >= calendarThrough, stop without appending that interval.
7. Require begin.Kind and end.Kind to be Utc, serialize unchanged, and read ActualTradingDayExchange for its date label. No timezone conversion is added.
8. Append the interval, set lastEnd=end, then query=end.AddTicks(1). Stop if query >= calendarThrough. If iteration 63 still needs another advance, throw; no 65th call occurs.
9. Only after calendar success, proceed to header/bar serialization and all existing bar, identity, ownership and seal guards. First/last returned bars remain excluded.

The traversal is extracted into a private method for deterministic testing; its input construction, guards, ordering and termination rules are unchanged. Diagnostic I/O remains fail closed.

## Failure attribution and bounded context

New success stages: CALENDAR_ITERATOR_CREATED, CALENDAR_QUERY_BEGIN, CALENDAR_ADVANCE_SUCCESS, CALENDAR_SESSION_BOUNDS_READ_SUCCESS, CALENDAR_QUERY_ADVANCED, CALENDAR_ITERATION_COMPLETE.

Distinct failures: FAILED_CALENDAR_ITERATOR_CREATE_EXCEPTION, FAILED_CALENDAR_ADVANCE_FALSE, FAILED_CALENDAR_ADVANCE_EXCEPTION, FAILED_CALENDAR_SESSION_BOUNDS_READ_EXCEPTION, FAILED_CALENDAR_TRADING_DAY_READ_EXCEPTION. Existing order, UTC-kind and iteration-limit guard failures retain their meaning. The bounds-read field identifies BEGIN versus END; a successfully read begin is retained even if reading end throws.

Each iteration flushes input before the native call. Rows carry zero-based iteration, query text/Kind, include-end flag, boolean outcome (TRUE, FALSE, or NOT_RETURNED), current bounds/Kind, last fully accepted query and bounds/Kind, request dates and Kinds, fixed template/timezone pins, returned row count and source index. Current bounds reset before every call, preventing stale bounds from appearing as current evidence. On QUERY_ADVANCED, calendar_query is the next query; last_successful_query is the query which produced the appended interval.

Native constructor, GetNextSession, bounds getters and trading-day getter may throw InvalidOperationException; their actual native exception conditions are not available in the installed reference metadata. Explicit local InvalidOperationException guards cover false returns, nonordered/nonadvancing bounds, non-UTC bounds, and exhausting 64 iterations. Trace can also throw on a missing diagnostic writer or exceeding its cap. Distinct success stages are set before diagnostic writes, so diagnostic I/O is not mislabeled as a native call exception. AddTicks/date arithmetic have their own stages and can produce range errors; no such error is promoted to an iterator false return.

The fixed diagnostic cap rises from 48 to 512 to accommodate up to four progress rows per iteration plus lifecycle, completion and terminal evidence. The original 64-iteration admission limit is unchanged. Strings are fixed categories, fixed identities or formatted DateTimes; native message text and stack traces never enter the file. exception_message is a bounded fixed false-return explanation or a full-redaction marker for native/guard exceptions. This is intentional sanitization, not a claim to preserve the original message. A synchronously hung native call cannot be bounded by a loop counter: its pre-call record survives, but no new timeout/thread-cancellation behavior is introduced.

## Time-domain investigation

Installed NinjaTrader.Core.xml 8.1.8.2 names BarsRequest parameters fromLocal/toLocal and SessionIterator input timeLocal. It describes ActualSessionBegin/End in the user's configured timezone. Official [GetNextSession documentation](https://docs.ninjatrader.com/ninjascript/getnextsession) describes a session query relative to timeLocal and a boolean success result. [BarsRequest documentation](https://docs.ninjatrader.com/ninjascript/barsrequest) describes the date-based request; [ActualSessionBegin documentation](https://docs.ninjatrader.com/ninjascript/actualsessionbegin) uses PC-local terminology, less precise than the installed configured-timezone wording.

With application timezone guarded to UTC, the supplied UTC wall-clock values are consistent with the installed configured-timezone description. Central Standard Time is the template/exchange timezone, not an instruction to pass Chicago wall time to this API. Native acceptance or conversion rules for DateTime.Kind Utc, Unspecified and Local are not established by these signatures. In particular, DateTimeKind.Local is not automatically the application's configured timezone. Do not substitute ToLocalTime, ToUniversalTime or another SpecifyKind call based on parameter names alone.

Reflection-only inspection confirms `Boolean GetNextSession(DateTime timeLocal, Boolean includesEndTimeStamp)` in SDK 8.1.8.2. The exposed body is `20-00-00-00-00-2A` (constant-zero return), not usable evidence of the running native implementation: the recorded native callback progressed through session reads. No SDK method was executed to infer its behavior. Returned bar Kinds remain unobserved in the failed capture because execution never reached bar serialization. The prior Utc field cannot resolve that missing evidence.

Conclusion: configured-timezone wall values are consistent; native Kind interpretation and the original failed query remain unproven. No behavioral correction is objectively justified offline.

## Offline validation and preservation

The actual C# exporter is compiled against SDK 8.1.8.2 using a name-only Indicator shim deriving the real IndicatorRenderBase; it is not installed or run inside NinjaTrader. Synthetic doubles separately exercise first session, normal advancement, coverage termination, daily break, weekend and Sunday reopen, false and throwing calls (including after successful iterations), individual bounds-read exceptions, constructor failure, reversed/repeated/nonadvancing bounds, and the 64-call limit. Alternate-Kind tests prove exact forwarding and diagnostics only, not native contract acceptance.

Committed R1 and R2 run against the same doubles for seven scenarios. Admission outcomes and emitted historical payloads (excluding random dataset UUID) must agree. R1 lifecycle/ownership/privacy tests remain in the suite. The certifier adds only the exact R2 authored-source digest, retaining both earlier reviewed hashes and rejecting unknown source; historical schemas and certification rules are unchanged. Diagnostics remain non-certifying and runtime_admission=false.

Exact commands, counts, source pins, SDK compile evidence, runtime observations and preservation results are recorded in `backend/tests/calendar_iterator_diagnostics_sprint16ar2.json` and ignored local evidence under `.arms-dev/sprint16a-r2/`. The old diagnostic capture and installed R1 source remain unchanged. No local commit is authorized for this phase.

## Human gate

Offline instrumentation is not a diagnosed native cause. Review this patch before a separately authorized historical-component installation/recompile and fresh capture preparation. No repeat capture is ready or armed. Production ArmsReadOnlyMarketV1 must remain untouched.
