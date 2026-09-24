# R5.3-F — Request configuration and loaded snapshot/calendar context

Status: offline implementation, not an Indicator, not native activation.
Uses A/B/C/D/E unchanged. A complete host and native-context envelope verifier
are still required before any real run. Synthetic results do not solve R2/R4.

## Ownership and configuration

SessionTimestampNativeContextV1 is bound to the actual host owner and to itself.
A shallow clone or a foreign owner cannot create, use or invalidate its original.
CreateAndWrap has one constructor-attempt allowance. It checks the live operator
settings, UTC application rules, Playback absence, installed Core version,
instrument and loaded template before constructing the one BarsRequest.

Request configuration is fixed: NQ DEC26, Minute/1 Last, Repository, DoNotMerge,
reset at EOD, no dividend or split adjustment, from 2026-09-16 through 2026-09-21.
These are LOCAL CALENDAR DATE parameters, not asserted UTC instants. The native
FromLocal and ToLocal clock fields must equal those dates; their observed Kind
is recorded and becomes part of the stable request configuration. No UTC Kind
precondition is imposed on these request property values.

A factory error after construction attempts one cleanup before returning any
resource. A successful return transfers the E wrapper to C's exclusive lifetime
management. F does not submit a request and does not dispose a successfully
transferred request. Invalidate only disables further context use. Full context
reads must occur before C/E closes the request; cached context bytes can be read
later without accessing disposed native objects.

Operator confirmations are declarations, not independent observations of market
flow or connection health. F checks their values and output-property identity;
D/future host remains responsible for safe local paths and private capture files.

## Loaded calendar, not a template name alone

Both the requested TradingHours and the returned Bars.TradingHours are examined.
They may initially be separate objects with identical content. After binding,
each object identity and its canonical content must remain unchanged.

The deliberately narrow reviewed schedule is five weekly sessions:
Sunday-to-Monday through Thursday-to-Friday, HHmm 1700 to 1600. Weekdays,
TradingDay and HHmm fields must match. This is an experiment prerequisite, not a
claim that no other valid CME template exists. A different schedule is rejected,
not silently substituted or repaired.

Canonical context includes the template name/version, session definitions,
all full-holiday date keys and partial-holiday rule fields (bounded collections),
the loaded TimeZoneInfo serialized rules and their SHA256. Holiday description
text is omitted because it is not a scheduling rule. The calendar limit is 4096
items per holiday collection, 32 sessions per partial holiday, 32768 bytes for
serialized zone rules and 65536 bytes for the canonical calendar.

For this experiment, any full or partial holiday in September 13–22, 2026 is a
failed prerequisite. F does not implement a general holiday engine. This
conservative policy avoids pretending that a weekly template alone certifies
reference dates in the presence of exceptional sessions.

A's explicit source-zone conversion is used only on reference wall clocks to
confirm the expected first and next session UTC boundaries. It rejects invalid
or ambiguous wall times and range saturation. No fixed -5/-6 offset is used by
F's implementation. A uses the same actual returned template zone for the query
plan. F does not call SessionIterator, GetNextSession or calendar helpers that
may hide additional iterator calls.

## Snapshot binding

Bind accepts the actual callback request identity and records the returned Bars
object. It measures the snapshot twice before publication, comparing count and
SHA256. Rows are bounded at 3–10002; 4503 and 5520 are tested examples, never
hard-coded native expected counts. The first actually returned timestamp must
have Kind.Unspecified for A_U; it is not relabelled to satisfy that prerequisite.
Other returned Kinds are observed as-is. Raw endpoint order must permit A's
existing range plan. Duplicates, decreases, Kind transitions and subminute ticks
are observed, not normalized or treated as trading-history admission evidence.

The source index for family A is exactly zero. Its ticks and Kind, raw endpoints,
row count, full snapshot hash, template hash and loaded zone are supplied to the
unchanged A plan. A/B/C and reference families retain their existing provenance.

Fingerprint version R53F_SNAPSHOT_BITS_V1 hashes UTF-8 bytes:
- Header `R53F_SNAPSHOT_BITS_V1|<count>\n`.
- Each row: index, raw DateTime ticks, numeric Kind, the signed IEEE-754 binary64
  bit patterns of Open/High/Low/Close, and integer Volume, separated by `|` and
  terminated with `\n`. Integers use invariant decimal formatting.

This version is different from previous probes' fingerprint algorithms. Never
compare hashes across algorithms as proof that snapshots differ or match.
The algorithm includes all getter values but does not assert OHLCV validity,
provider provenance, bar completeness or historical admissibility.

Light checks before E's native actions verify gates, request properties, loaded
calendar content, selected Bars identity/count and raw endpoint identity. Full
scans also occur at matrix entry/completion and lifecycle preparation boundaries.
These are observation-point checks; they cannot prove that no transient change
occurred and reverted between checks. Cooperative cancellation cannot atomically
prevent an SDK call that was already in flight.

Failures latch the context unusable. Fixed guard identifiers, operation labels,
safe exception classes and the current source index are exposed for the future
host's failure trace. Native messages/stacks are not persisted. F itself writes
no trace or seal.

## Integration and evidence boundaries

Synthetic integration covers real A/B/C/D/E/F source against explicit SDK doubles.
C invokes F's configuration factory, E submits the fake request, F binds actual
fake Bars values, A creates the plan, B/E execute the matrix, F revalidates, and D
prepares/closes/seals the matrix. The unchanged D verifier accepts the results.
Request, constructor, query and bounds counters are compared with the doubles.

The integration writes an extra `context.json` beside, not inside, D's capture
folder. Python tests independently reconstruct the known synthetic snapshot
hash and compare it and the template hash with D's sealed plan. This extra file
is a TEST ARTIFACT, NOT a completed native-context evidence envelope. D's seal
does not bind those extra bytes. A future host/verifier must durably bind full
context, identifiers and matrix bytes without weakening D's file-ownership rules.

Context JSON is capped at 131072 bytes; a future native envelope must fragment or
bound it to the design's per-record and overall evidence ceilings. No claim is
made that this whole context can be placed into a single 32768-byte D record.

## Validation scope

103 C# cases plus one aggregate inventory, 18 context/matrix crosschecks, a
structural test, an installed SDK compile test and two F1 mutation controls give
126 pytest cases. With unchanged A–E this is 521 combined cases, not 521 new cases.

The SDK-linked library is compiled against installed Core/Gui 8.1.8.2 and never
executed. Only the executable referencing framework libraries and explicit SDK
doubles runs in this package. Namespace imitation in the doubles is synthetic;
no test establishes the real GetNextSession false-return predicate.

The package preserves all earlier sources and evidence, uses new UUID audit
folders, refuses different existing target contents and never deletes, stages,
commits, pushes, restarts services or edits the NinjaScript installation.

## Remaining before a native run

A disabled-default NinjaScript Indicator must compose these components after
DataLoaded, keep UI clones from touching original resources, publish a complete
native-context binding with the closed matrix, and enforce current operator and
isolated-target prerequisites. Its end-to-end lifecycle, evidence/verifier and
SDK compile require separate validation. Native activation remains unauthorized.

## Official contracts consulted

- https://ninjatrader.com/support/helpguides/nt8/barsrequest.htm
- https://ninjatrader.com/support/helpguides/nt8/request.htm
- https://ninjatrader.com/support/helpguides/nt8/tradinghours.htm
- https://ninjatrader.com/support/helpguides/nt8/tradinghours_sessions.htm
- https://ninjatrader.com/support/helpguides/nt8/partialholidays.htm

The date constructor requests full trading days, not arbitrary UTC subranges.
These docs describe supported API surfaces; installed version-specific compile
and native observation remain separate requirements.

## F1 repair review — harness dispatch only

The initial F package's private run reported 102/103 passing C# cases.
The only failure was `bind_repeated` with
`Exception:EXPECTED_CONTEXT_REJECTION`; promotion did not occur.

The cause is in the synthetic harness dispatcher: the earlier
`name.StartsWith("bind_", StringComparison.Ordinal)` branch captured
`bind_repeated`. That branch injected no fault for the suffix `repeated`,
then expected the FIRST valid Bind to be rejected and returned. Consequently,
the intended second-Bind branch after `var plan = u.Bind()` was never reached.

F1 excludes `bind_repeated` from the invalid-first-bind prefix branch and keeps
all 103 original cases. Its second-Bind case now explicitly requires:
- successful first Bind;
- second Bind rejected with `SNAPSHOT_ALREADY_BOUND` and failure latched;
- no new snapshot scans, timestamp reads, request creation/submission or iterator
  actions on that rejected call;
- no premature disposal of the original request and no changed captured bytes;
- later Revalidate rejected as unusable without extra reads;
- disposal exactly once by the legitimate request owner.

The production-context candidate is BYTE IDENTICAL to the failed F package:
SHA256 d3d8eddd9ed0daea524730c9bf3ab7a3f626cb37ff4c688d1e9d2096b6b1cbe5.
Its existing `Require(!bound,"SNAPSHOT_ALREADY_BOUND")` guard is not weakened,
removed or replaced. No native behavior change is made for this repair.

Two additional mutation tests compile PRIVATE copies with that guard removed
or forced to reject the first Bind. Both must make the targeted harness case
FAIL for the expected reason. An intentionally failed mutant is a passing
negative control, not approval of changed production code.

The F1 installer runs both negative controls before promotion, after the
original 103 C# cases and 18 sample crosschecks pass. It then runs 521 combined
pytest cases (395 unchanged A–E plus 126 F1), with zero failures/errors/skips
required. Until actual runtime results pass, this remains a candidate repair.

The original failed F audit and files are preserved byte-for-byte in place.
New audit outputs use a fresh core-f1 UUID directory. No original package, logs,
capture or source is overwritten. If an existing repository target differs,
the installer stops instead of restoring or replacing it.

This resolves the identified TEST ROUTING defect only. It does not establish a
native GetNextSession false-return predicate or authorize a native experiment.
