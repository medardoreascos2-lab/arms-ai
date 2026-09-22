# ARMS AI — Sprint 16A-R5.3
# SessionIterator Timestamp Interpretation Experiment

## Status

Design only.

No R5.3 source has been implemented.
No native R5.3 execution has occurred.
No exporter repair is authorized.

## Established evidence

### R2 / R4

Independent SessionIterator experiments established that initial
GetNextSession calls succeeded, while subsequent queries returned false
without exception.

The exact false-return predicate remains unresolved.

### R5.1

The domain probe returned repository bars but failed closed during coverage
validation because the first returned Bars.GetTime timestamp was not UTC.

R5.1 therefore never reached its SessionIterator matrix.

### R5.2

A dedicated timestamp-domain probe completed successfully and was accepted
by the committed offline verifier.

Native R5.2 observations:

- returned rows: 5520
- DateTimeKind.Unspecified: 5520
- DateTimeKind.Utc: 0
- DateTimeKind.Local: 0
- Kind transitions: 0
- duplicate adjacent timestamps: 0
- decreasing adjacent timestamps: 0
- minute misalignment: 0
- SessionIterator calls: 0
- timestamp conversions: 0
- application timezone: UTC

First raw timestamp:

`2026-09-15T22:01:00.0000000`

Kind:

`Unspecified`

Last raw timestamp:

`2026-09-21T21:00:00.0000000`

Kind:

`Unspecified`

R5.2 establishes the cause of the R5.1 coverage failure:
the R5.1 UTC-Kind precondition did not match the native BarsRequest
timestamp domain.

R5.2 does NOT establish the cause of the R2/R4 GetNextSession false return.

## Purpose

R5.3 exists only to determine whether explicit DateTime interpretation
changes SessionIterator behavior for carefully bounded queries.

It must distinguish:

1. raw native Unspecified DateTime
2. the same raw clock fields explicitly labelled UTC
3. the same raw clock fields interpreted using the TradingHours timezone
   and then represented in UTC

These are experimental controls.

None is authorized as production behavior.

## Critical interpretation rule

R5.3 must never silently normalize timestamps.

Every transformed query must preserve:

- original raw DateTime
- original DateTime.Kind
- interpretation method
- interpreted DateTime
- interpreted DateTime.Kind
- raw ticks
- interpreted ticks
- tick delta

The experiment must describe interpretation, not repair.

## Native source

Use exactly one repository-only BarsRequest matching R5.2:

- instrument: NQ DEC26
- Minute / 1
- Last
- Trading Hours: CME US Index Futures ETH
- Lookup: Repository
- Merge: DoNotMerge
- application timezone gate: UTC
- Playback prohibited

The request exists only to obtain real covered timestamps.

## Query families

Select bounded source timestamps from the returned snapshot.

At minimum:

### Family A — Covered timestamp

A real timestamp known to exist in the BarsRequest snapshot.

### Family B — Session-end-relative timestamp

A timestamp selected relative to a known session boundary without using
a previously mutated SessionIterator.

### Family C — Maintenance-gap timestamp

A timestamp corresponding to the previously investigated maintenance gap.

Each family must retain its source/provenance.

## Interpretation variants

For each selected raw timestamp, construct isolated controls.

### U — Raw Unspecified

Use the native DateTime exactly as returned.

No conversion.
No SpecifyKind.

### LUTC — Label same clock fields as UTC

Create an experimental DateTime with identical calendar/clock fields and
DateTimeKind.Utc.

This is a label/control only.

It must not be described as proving that the raw value means UTC.

### THUTC — Interpret clock fields in TradingHours timezone

Treat the raw clock fields as belonging to the loaded TradingHours timezone,
then derive the corresponding UTC instant using an explicit,
auditable conversion.

This is an interpretation control only.

It must not be used by production code.

## SessionIterator isolation

Every GetNextSession call must use a fresh SessionIterator unless a
separately named reuse control is explicitly included.

No result may depend on hidden state from a previous experimental variant.

Persist iterator identity/control ordinal.

## Constructor controls

Where bounded and justified, compare:

- SessionIterator(Bars)
- SessionIterator(TradingHours)

Constructor comparisons must use separate iterators.

## End-inclusion controls

Where relevant, compare includeEndTime:

- true
- false

Do not multiply the matrix beyond the explicit native-call budget.

## Native call budget

R5.3 must remain bounded.

Maximum:

- one BarsRequest
- twelve GetNextSession calls
- twelve SessionIterator instances

The implementation may use fewer.

Any path that would exceed the budget must fail closed before the extra call.

## Required observations per GetNextSession call

Persist:

- case id
- query family
- interpretation variant
- constructor context
- iterator identity/ordinal
- includeEndTime
- source index if applicable
- raw source timestamp
- raw source Kind
- raw source ticks
- interpreted query
- interpreted query Kind
- interpreted query ticks
- interpretation tick delta
- GetNextSession Boolean result
- SessionBegin if result true
- SessionEnd if result true
- returned bound Kinds
- exception type/message
- guard result

Do not read session bounds after a false return.

## Success criteria

R5.3 is diagnostic.

A successful experiment means:

- the bounded matrix completed
- evidence was sealed
- the verifier accepted lifecycle/integrity
- every query/result is attributable to its interpretation variant

It does NOT require any variant to return true.

## Causal interpretation

Only a controlled difference where:

- source clock fields are held constant
- iterator context is isolated
- includeEndTime is held constant
- constructor context is held constant
- only interpretation differs

may support the statement that DateTime interpretation affects observed
SessionIterator behavior for that tested query.

Even such a result does not automatically authorize a production repair.

## Prohibited conclusions

R5.3 must not claim that:

- Unspecified means UTC
- Unspecified means TradingHours local time
- one interpretation is universally correct
- SessionIterator requires UTC
- SessionIterator requires TradingHours-local timestamps
- the historical exporter should be changed
- historical data is admissible
- trading/execution authority exists

unless separately established by later evidence and review.

## Safety

R5.3 must contain:

- zero account access
- zero order APIs
- zero ATM APIs
- zero execution authority
- zero connection mutation
- zero exporter mutation
- zero FreshNativeAdapter mutation

It must not submit trades or access broker accounts.

## Evidence

Use a fresh private output directory.

Successful evidence must include:

- JSONL trace
- completion seal
- SHA256
- byte count
- record count
- probe UUID
- request UUID
- BarsRequest count
- SessionIterator count
- GetNextSession call count
- diagnostic_complete=true
- writer_closed=true

The offline verifier must fail closed on contradictory or resealed evidence.

## Preservation

R2, R3, R4, R5, R5.1 and R5.2 evidence and committed sources are immutable
inputs to this experiment.

R5.2 native evidence must not be reused as an R5.3 output directory.

## Implementation gate

Implementation requires a separate review after this design is inspected.

No installation or native activation is authorized by this document.


## Review addendum R5.3-A — explicit experimental controls

Status: DESIGN_REVIEWED_NOT_IMPLEMENTED.

This addendum proposes a narrower implementation contract.
It supersedes the earlier optional matrix expansion where they conflict.
It adds no native findings and authorizes no installation or execution.

### Evidence interpretation correction

R5.1 established a DateTime.Kind precondition mismatch.
It did not establish that an Unspecified clock value denotes a non-UTC
instant.

R5.2 characterized one later snapshot of 5520 rows.
Do not assume a future request returns 5520 rows, or that it reconstructs
the earlier R2/R4/R5.1 snapshot.

### Separate Kind effects from clock/tick effects

U versus LUTC:
- identical raw ticks and clock fields;
- different Kind only;
- no timezone conversion.

LUTC versus THUTC:
- both output queries have Kind.Utc;
- THUTC uses an explicitly stated source-zone interpretation;
- record the actual tick delta;
- a changed result is not evidence of a Kind-only effect.

Do not describe all variants as representing the same instant.

THUTC must check the loaded source zone for ambiguous/invalid wall times.
Do not silently choose an offset. If interpretation is ambiguous, invalid
or outside DateTime range, stop before executing the native matrix.
Do not hard-code a daylight-saving offset.

### Fixed query families and provenance

A: exact Bars.GetTime(0) from the new request.
Persist index, raw ticks and Kind, and the current snapshot fingerprint.
The U control requires that this actual value is Unspecified.
If not, stop with an explicit prerequisite diagnostic; do not relabel it
and call it native-Unspecified evidence.

B: reference clock fields 2026-09-14T21:00:00.0000000, taken from
the previously reported successful R2/R4 session-end boundary.

C: reference B plus exactly one tick:
2026-09-14T21:00:00.0000001.

For B/C, persist the original UTC reference separately.
Their U variants are deliberately constructed Unspecified clock controls,
not native Bars.GetTime values. source_index must be null.

B/C must not be claimed to lie within the new Bars snapshot.
Persist raw range comparisons without implying timezone-normalized
coverage or membership.

### Fixed scheduling and budget

Use SessionIterator(Bars) and includeEndTime=true throughout.

01 A_U       fresh iterator I01
02 A_LUTC    fresh iterator I02
03 A_THUTC   fresh iterator I03
04 B_U       fresh iterator I04
05 B_LUTC    fresh iterator I05
06 B_THUTC   fresh iterator I06
07 C_U       fresh iterator I07
08 C_LUTC    fresh iterator I08
09 C_THUTC   fresh iterator I09
10 R0        fresh iterator I10; query 2026-09-14T00:00:00Z
11 R1        reuse I10; query exactly C_LUTC
12 N         fresh iterator I11; query 2026-09-14T22:01:00Z

R1 executes only after R0 returns true with readable, valid bounds.
Otherwise record a justified skip; do not create a replacement iterator.

N is an interior-time expectation from the reviewed template, not an
already observed native session bound.

Before native execution, verify that the loaded template supports the
reference calendar expectations. Do not derive them by making hidden
extra SessionIterator calls.

Maximum: one BarsRequest, twelve GetNextSession calls, eleven iterators.
Count constructor attempts and method-call attempts before invocation.
No retries or additional calendar helper calls are authorized.

TradingHours-constructor and includeEndTime=false comparisons are
deferred, not optional additions to this matrix.

### Interpretation limits of the comparisons

Compare C_LUTC versus R1 only as a fresh-versus-reused control on the
same new Bars snapshot with the same query ticks, Kind and inclusion flag.

Compare the complete R0/R1 results with preserved R2/R4 observations.
A changed snapshot or unmatched initial bounds prevents claiming an
exact reconstruction of the earlier failure.

False returns are diagnostic outcomes, not proof of a timezone defect.
Do not read bounds after false. Distinguish constructor failure, native
call exception, false return and bounds-read exception.

### Lifecycle, integrity and verifier requirements

Use a new component; do not modify prior probes or exporters.

Bind selected observations to the fingerprinted snapshot. Recheck Bars,
request settings, loaded template identity and fingerprints before
completion. A changed snapshot or configuration must prevent completion.

Preserve original timestamp precision and Kind in every observation.
Record conversion method, source-zone identity, offsets and tick deltas.

Native/provider exception messages and stacks must not be persisted.
Use fixed guard identifiers, safe exception types and bounded context.

Clones must not write to or dispose another instance's request/writer.
Do not treat destruction of the original by a clone as a passing
isolation test. Test owner preservation explicitly.

Validate normal and inline callback ordering without allowing early
completion. Test duplicate/reentrant callbacks and request failure after
an inline callback.

Verifier requirements include exact field/type checks, rejecting bool
or float values where integers are required, query/tick/Kind consistency,
source-index binding, case order, iterator ownership, counters, justified
skips and seal hash/length/count consistency.

A seal verifies byte integrity and internal consistency only within the
implemented checks. It does not independently prove native provenance,
the truth of omitted observations, timezone meaning or data admission.

Cap evidence at 96 records, 262144 bytes and 32768 bytes per record.
Cap the seal at 4096 bytes. No record-per-bar logging.
Keep wrapper stdout and audit logs outside the capture directory.
Never overwrite or delete earlier captures.

### Next gate

Review this fixed plan before implementation.
Only the design document is changed by this review.
No commit, native rerun, installation or exporter change is authorized.
