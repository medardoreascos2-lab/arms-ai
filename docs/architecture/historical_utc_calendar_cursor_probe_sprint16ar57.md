# R5.7 historical UTC calendar cursor diagnostic

Status: offline implementation. No installation, native run, production repair,
source-pin update, certification admission, PAPER or LIVE authority is granted.

## Purpose and prior evidence

R5.6 observed one ordinary UTC transition in both fresh and primed/reused
iterators. End,true repeated the prime; End,false and End+1tick with either flag
returned false; Q0+1day,true advanced. This does not prove a general strategy,
explain native internals, or justify ignoring false in production.

R5.7 captures a complete independent daily UTC query schedule using one returned
repository Bars object. It compares one reused iterator against one fresh
iterator per query. Agreement alone is insufficient: the independent verifier
reconstructs the expected calendar and checks exact ordered interval equality.

## Six-file isolation

- `integrations/ninjatrader/HistoricalUtcCalendarCursorDiagnosticV1.cs`
- `integrations/ninjatrader/ArmsHistoricalUtcCalendarCursorProbeV1.cs`
- `tools/verify_historical_utc_calendar_cursor_v1.py`
- `backend/tests/fixtures/historical_utc_calendar_cursor_harness_sprint16ar57.cs`
- `backend/tests/test_historical_utc_calendar_cursor_probe_sprint16ar57.py`
- This document.

No runtime dependency on R5.3/R5.4/R5.5/R5.6 diagnostics, pinned fixtures or backend
certification is introduced. Reviewed R5.6 lifecycle and publication patterns
were copied into the new host and adapted locally. Existing sources remain
unchanged. SDK compile-only builds write to pytest temporary directories and do
not load or launch NinjaTrader.

## Request and schedule contract

One BarsRequest: NQ DEC26, expiry 2026-12-01, master NQ, tick size .25, point value
20; Minute/1/Last; Repository lookup; DoNotMerge; reset on new trading day;
dividend/split adjustments false. TradingHours is CME US Index Futures ETH with
Central Standard Time. Application timezone must be UTC; playback is rejected.
Request identity, callback identity, returned instrument/period/calendar and SDK
version 8.1.8.2 are checked. Full assembly identity and MVID are recorded, not
represented as attestation.

The properties are disabled/empty by default: enabled, private output directory,
From UTC date, Through UTC date, operator repository/connection confirmation.
Dates parse as Unspecified date identifiers, just as the historical request.
Both configured dates must be in 2026, ordered, with a span of at most 14 days.
No timestamp coming from Bars is relabeled or converted.

Before any iterator construction:

```
C0 = SpecifyKind(configured From.AddDays(-2), Utc)
C1 = SpecifyKind(configured Through.AddDays(8), Utc)
schedule = C0, C0.AddDays(1), ..., C1 inclusive
N = configured date difference + 11
11 <= N <= 25
```

All dates are midnight, all query Kinds are Utc, includeEndTime is always true,
ordinals are zero-based, and derivation is UTC_CALENDAR_DATE_CURSOR. Arithmetic
overflow, non-date input, unsupported input Kind or over-budget schedule fails
before traversal. No native session end participates in query generation.

REUSED runs first, with one constructor; FRESH then uses N independent
constructors without priming. Every constructor receives the identical returned
Bars reference. Full runs therefore have N+1 constructors and 2N calls, bounded
by 26 and 50. Constructor ordinals are global, one-based, attempt identities.
Constructor completion is separately recorded. Each call records attempted and
completed GetNextSession counts and attempted getter counts; successful returned
fields indicate completed getters. There are no hidden session helper calls.

## False, exceptions and completion

False is a raw observation with no bound/day getters. The next *predeclared*
date is still queried. This is diagnostic observation, never production fallback
or a retry. All-false captures can pass integrity with coverage false.

True reads begin once, end once, then checks ordering and UTC Kind, then reads
exchange trading date once. Its raw Kind/ticks are retained. Unlike the exporter,
the diagnostic also observes the final inclusive boundary query; it does not
apply a terminal shortcut before that query's UTC/day validation.

Native constructor/call/getter exceptions are reduced to a closed category; no
provider message is emitted. They stop that path. An independent FRESH path may
still run after REUSED stops. Invalid bounds also stop their path. Context or
cancellation failures abort the host. Any incomplete path prevents a completion
seal. Partial body observations may be retained but cannot verify as completed.

## Captured calendar binding and independent expectation

Each request/returned-calendar snapshot contains name/version/timezone plus:

- `calendar_rules_json`: ordered session definitions, sorted raw holiday dates,
  sorted partial-holiday dates/flags/constraints/session definitions.
- `timezone_rules_json`: zone ID, base UTC offset, DST support and complete public
  adjustment-rule fields for rules intersecting 2025 through 2027: date limits,
  daylight delta, fixed/floating transition month/day/week/weekday/time ticks.
- SHA256 of the exact UTF-8 bytes of each embedded JSON string.

No hash-only calendar is accepted. Request and returned calendar facts must
match; repeated context checks detect changes. Adjacent years cover the existing
lookback/lookahead at January/December request edges.

The Python verifier derives expectations exclusively from these captured rules.
It does not use the installed machine timezone, NinjaTrader, a copied expected
native result, the pinned XML fixture, or backend admission code. Its independent
rule evaluator converts *calendar wall definitions* to expected UTC instants;
this is not conversion of any query or bar timestamp.

The supported fail-closed calendar shape follows the reviewed backend scope:
session end day equals trading day; full holidays suppress that trading date;
early-end partial holidays may shorten the configured end, with no late begin
or replacement-session collection. Unsupported exceptions, duplicate rules,
overlapping calendars and invalid bounds reject verification.

The timezone evaluator supports a positive integral-minute daylight delta,
northern start-before-end transitions, and one applicable adjustment rule
covering each evaluated whole year. Fixed and floating transitions are supported.
Unsupported/overlapping/missing/part-year rules reject verification. Ambiguous
and nonexistent calendar wall times reject; neither fold is silently chosen.
This bounded evaluator is not a general replacement for a timezone library.

Expected tuples are `(begin_ticks, Utc, end_ticks, Utc, trading_date_ticks,
Unspecified)`. The expected trading date is a date identifier, not a converted
native timestamp. A different raw native day Kind is preserved and yields
coverage false. The target window uses the backend's `end >= C0 && begin < C1`
membership rule. Actual ordered tuples must equal expected tuples exactly.

Identical adjacent tuples are deduplicated only for comparison; raw calls remain
intact. Nonadjacent returns to an earlier session, contradictory duplicate bounds,
backwards ends and overlapping intervals reject verification. Missing/extra
in-window sessions or differing valid bounds yield coverage false. Advancing
ends alone never imply completeness.

## Raw artifacts versus derived analysis

The native body declares `analysis_location=INDEPENDENT_OFFLINE_VERIFIER`.
Calendar expectation, coverage, deduplication, comparisons and summaries are
computed by the verifier and emitted in its JSON stdout report. They are not
duplicated as potentially inconsistent native claims. Native summary/coverage
fields added to the closed schema are rejected, even when resealed.

The report contains all schedule/count/false/success/exception/coverage and
preservation summaries, raw-result comparison categories, the expected interval
list, deduplicated in-window lists, false-to-next-success links and range regions.
Exceptions and unobserved ordinals cannot be counted as ordinary matching results.

Range regions use configured From midnight through the day after configured
Through midnight: LOOKBACK, REQUEST_OVERLAP, LOOKAHEAD. This is a descriptive date
partition, not permission to export additional bars. Raw final-query returns
outside the calendar target remain visible but are excluded from coverage.

Date tags derive from captured rules and actual scheduled date identities:
ORDINARY, FRIDAY, SATURDAY, SUNDAY, FULL_HOLIDAY,
PARTIAL_HOLIDAY_OR_SPECIAL, DST_TRANSITION_WINDOW, RANGE_START_EDGE,
RANGE_END_EDGE. Weekday/holiday tags describe the date identifier, not a claim
that a UTC midnight instant is inside an exchange session. DST tags cover the
captured transition date and its adjacent dates. No class is fabricated to make
a run appear complete, and no requirement forces all classes into one run.

## Publication and authority

Output must be a fresh pre-existing empty private local fixed-drive directory,
without reparse ancestors. Final files are exactly:

```
historical-utc-calendar-cursor.json
historical-utc-calendar-cursor.done.json
```

The writer reserves with CreateNew, flushes body/seal, uses non-overwriting final
renames and retains incomplete artifacts. It never deletes, repairs, substitutes
filenames or retries. Atomic monotonic cancellation shares a short ordering gate
with final-seal rename. Cancellation admitted first prevents final publication.
Duplicate callbacks and rearming are suppressed; request disposal precedes seal.

The verifier accepts only the exact final pair and rejects temporary seals,
extra files, directories/redirected artifacts, bad hashes/lengths, duplicate JSON
keys, noninteger ticks and resealed graph contradictions. Byte validation alone
does not establish publication; the completed-capture entry point does both.
The operator must keep the capture directory private/stable during verification.

Every envelope/report is DIAGNOSTIC_ONLY / OPERATOR_NATIVE_RUN_UNATTESTED.
Native provenance attested, certification evidence, runtime admission, execution
authority, exporter invoked/change, stored timestamp mutation, Bars mutation,
TradingHours mutation, PAPER and LIVE remain false even when coverage matches.
Hash integrity cannot authenticate native provenance or resist a coherent forged
capture; the schema deliberately grants no such authority.

## Offline checks and next gate

Run new tests, the prior ten-file baseline, then both together with:

```
py -B -m pytest -q -p no:cacheprovider <explicit test files>
```

Tests execute these new C# files against synthetic SDK doubles and independently
check counters/getter order, schedule, request identity, preservation, calendar
expectations, mismatch/false/duplicate cases, lifecycle races, artifact integrity
and adversarial resealing. An installed-SDK compilation test performs no native
execution. Synthetic results never count as native strategy evidence.

Next gate is adversarial review of these six new files. Any installation or
native run needs separate authorization. Later runs may cover ordinary/weekend,
closure/early-close, spring DST and fall DST in separate explicit ranges, one
request and fresh output each. Calendar/date availability must be checked before
selection; no automatic request chaining or range/contract substitution exists.

Even successful future coverage does not repair the historical exporter's
separate raw bar Kind gate, authorize source-pin changes, certify backend
admission, or enable PAPER/LIVE.
