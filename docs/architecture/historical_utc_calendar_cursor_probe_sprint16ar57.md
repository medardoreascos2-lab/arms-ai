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
or replacement-session collection. Unsupported relevant exceptions, duplicate
rules, overlapping calendars and invalid bounds reject verification.

### R5.7-C special-session relevance

Global validation and semantic support are separate. Every raw partial remains
in the captured JSON, exact-byte calendar hash and body/seal binding, including
irrelevant partials. All dates, ordering, uniqueness, flags, constraint fields
and replacement-session fields receive strict structural validation. A nullable
constraint or replacement list is structurally representable, not evidence of
supported evaluator semantics. Recurring sessions still require
`end_day == trading_day`; generic constraints do not. Inactive constraint fields
are validated but never normalized or interpreted as active endpoints.

The old global early-only predicate rejected the captured 2024-12-25 late-open
record before computing coverage. Reusing recurring validation also rejected
its inactive `end_day=0` versus `trading_day=3`. Neither rejection established
that this distant record could influence the September 2026 comparison.

`special_influence()` proves a finite envelope only for a single endpoint edit:
exactly one of early/late, no replacement sessions, a nonnull constraint whose
active endpoint and trading weekday map to the named date, and one ordered,
nonoverlapping recurring session per trading weekday. Each recurring session
can cross midnight once. Split groups, longer groups, unknown mappings,
combined edits and replacements deliberately have no finite proof.

For this supported proof shape, the envelope encloses the complete preceding,
current and following recurring trading-date groups plus the active constraint
endpoint. Weekday lookup comes from the captured schedule, including week wrap;
these are not arbitrary date padding or a partial-date membership test. Closed
dates do not shrink the enclosure. The groups cover crossing sessions and the
neighbor that a late start after the ordinary end might affect. Min/max possible
UTC offsets are derived from the captured base and daylight deltas, requiring
continuous captured adjustment-rule coverage over the entire local enclosure.
Its rule date extents may prove offset bounds outside 2025..2027 without asking
the exact wall-time evaluator to evaluate those years. No machine timezone or
native observed session enters this calculation.

For local extremes `a,b` and possible offsets `O`, the UTC enclosure is
`L=ticks(a)-max(O), U=ticks(b)-min(O)`. A rule is potentially relevant exactly
when `U >= C0 && L < C1`. Touching C0 is relevant; touching only C1 is not.
Failure to prove the finite enclosure (including unavailable offsets or date
overflow) is relevant and fails closed. Relevant late-open, replacement and
combined semantics remain unsupported; relevant early-close constraints still
must satisfy the existing end-day, shortening and bound-order checks. Only the
derived evaluator selection excludes proven irrelevant records; raw evidence
is untouched. The existing recurring-date enumeration padding is not used as
the relevance proof.

For the captured 2024-12-25 late-open shape, the enclosure includes local
2024-12-23 17:00 through 2024-12-26 16:00. Captured possible offsets -06:00/-05:00
give UTC bounds 2024-12-23 22:00 through 2024-12-26 22:00, disjoint from the
September 2026 comparison. This proves irrelevance for this window, not support
for evaluating a late-open session in another window.

R5.7-C changes only this verifier, its Python test file and this document. No C#,
exporter, pins, raw capture, installation or admission behavior changes. Tests
exercise the captured late-open structure, relevant and neighboring failures,
unknown influence, both tick boundaries, malformed irrelevant records, exact
early-close/full-holiday expectations, strict recurring semantics, all binding
layers and observation independence. Synthetic mutations occur only in copies;
an optional read-only hash check verifies the operator capture when present.

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

The R5.7-C next gate is adversarial review of the verifier relevance proof and
its tests/documentation against the unchanged native artifacts. Any installation or
native run needs separate authorization. Later runs may cover ordinary/weekend,
closure/early-close, spring DST and fall DST in separate explicit ranges, one
request and fresh output each. Calendar/date availability must be checked before
selection; no automatic request chaining or range/contract substitution exists.

Even successful future coverage does not repair the historical exporter's
separate raw bar Kind gate, authorize source-pin changes, certify backend
admission, or enable PAPER/LIVE.
