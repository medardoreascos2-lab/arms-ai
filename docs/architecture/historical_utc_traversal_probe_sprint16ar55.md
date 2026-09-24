# R5.5 historical UTC traversal diagnostic

Status: offline implementation only. No installation, native run, production
integration, source-pin change, PAPER or LIVE authorization is granted here.

## Question and boundary

The unresolved question is what the native SessionIterator actually returns
for the historical exporter's UTC sequence on returned repository Bars.
Passing synthetic tests does not answer that question or explain a native false
return. R5.4's Unspecified wall-clock comparison addresses a different source.
PreserveUtc would leave both ticks and Kind unchanged and is not a repair.

The reference is ArmsHistoricalBootstrapV1 at commit
`c5ae6b3386111048f5b3224f3d2a512665f011a0`: BeginAttempt date parsing (152–156),
request construction (90–104), Completed request/Bars validation (347–383), and
CalendarIntervals traversal (214–267). No reference implementation is edited
or invoked by this package.

## Six isolated files

- `integrations/ninjatrader/HistoricalUtcTraversalDiagnosticV1.cs`: traversal,
  exact timestamp records and bounded native exception classifications.
- `integrations/ninjatrader/ArmsHistoricalUtcTraversalProbeV1.cs`: new opt-in
  request owner, context and snapshot checks, private publication.
- `tools/verify_historical_utc_traversal_v1.py`: independent byte/schema/sequence
  verifier; no backend certification import or admission capability.
- `backend/tests/fixtures/historical_utc_traversal_harness_sprint16ar55.cs`:
  explicitly synthetic SDK doubles compiling the actual new C# files.
- `backend/tests/test_historical_utc_traversal_probe_sprint16ar55.py`: runtime,
  contradiction, preservation, lifecycle and compile-only checks.
- This document.

The host owns a minimal one-shot request directly. R5.3's cursor/context is
bound to a predefined interpretation matrix; R5.4 requires Unspecified input.
Neither package is linked, imported, changed or reinterpreted here.

## Operator and request contract

All enable/confirmation booleans default false; output/from/through default
empty. One DataLoaded opportunity is consumed even when disabled. Property
changes, duplicate callbacks, repeated lifecycle notifications and running
instance clones cannot rearm an attempt. Termination intent is monotonic and
is published with Interlocked before acquiring the long-held state lock.
Traversal/context checkpoints and publication observe it. A separate short
gate orders intent admission against the final seal rename; neither traversal,
snapshot work, evidence writes nor file flushes holds that gate. Intent admitted
before that commit prevents a final seal. Termination after the commit cannot
undo an already published seal. No partial files are deleted.

A later, independently authorized native run would require explicit dates and
a fresh pre-existing empty private directory on a fixed local drive, plus
operator confirmation that repository data is ready and the connection is
stable. The host does not require a market-open assertion: the reference uses
repository history. It checks application timezone ID `UTC` and rejects
playback, without changing a connection or application setting.

Configured dates use the reference's invariant `yyyy-MM-dd` parse, both in
2026, inclusive order, at most 14 days apart. Parsed dates are Unspecified;
their exact ticks and Kinds are captured separately from the SDK's actual
FromLocal/ToLocal values. Dates are operator-supplied, not hardcoded.

Exactly one request targets NQ DEC26 (NQ, expiry 2026-12-01, tick .25, point
value 20), Minute/1/Last, CME US Index Futures ETH, Repository, DoNotMerge,
reset=true, dividend/split adjustments=false. Returned request identity,
instrument, period, count 3..10002, and TradingHours name/version/timezone are
checked. The request and returned calendar rule fingerprints must also agree.
The iterator receives returned request Bars, never chart Bars.

## Exact UTC traversal

The initial query is precisely
`DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc)`; the requested limit
is precisely `DateTime.SpecifyKind(through.AddDays(8), DateTimeKind.Utc)`.
These are the reference's configured-date constructions, not normalization of
unexpected runtime timestamps. All subsequent queries are native end plus one
tick, retaining UTC Kind. There is no adapter, timezone conversion, local-zone
lookup, relabeling of native bounds or alternative constructor.

One SessionIterator(returnedBars) is reused for at most 64 calls, always with
includeEndTime=true. The source record is added in memory before each call;
the value's ticks and Kind are checked before/after. False returns stop without
reading either bound or the trading day. On true, each bound is read once.
Begin must precede end and end must advance past the previous end. The reference
then stops if begin >= requested limit, before UTC validation and before the
trading-day getter. Otherwise both bounds must be UTC, followed by exactly one
ActualTradingDayExchange read, then end.AddTicks(1), then the end-based limit
check. The diagnostic reproduces that order, including terminal look-ahead.
Native exceptions stop immediately; provider text, paths and stacks are never emitted.
Context failures propagate to the host and prevent a seal rather than being
misclassified as native observations.

The trading-day value is recorded with its exact native clock, ticks and Kind;
it is never converted or relabeled and need not be UTC. A throwing getter ends
the observation at TRADING_DAY_READ, with no query update or next advance.
This is getter parity only; no native getter side effect is asserted.
For terminal look-ahead, bounds_valid means ordering passed; it does not claim
UTC Kinds were checked. For ordinary iterations it also requires UTC bounds.

The limit is a bound on call count, not a timeout for an individual native call.
No timer, background cancellation or forced interruption of native code exists.

## Evidence and preservation

Successful publication yields only:

- `historical-utc-traversal.json`
- `historical-utc-traversal.done.json`

Both explicitly carry DIAGNOSTIC_ONLY, OPERATOR_NATIVE_RUN_UNATTESTED and all
false provenance/certification/admission/execution/mutation flags required by
the request. A seal establishes complete bytes and contract integrity only.
Synthetic harness outputs have the same wire shape to test the real writer;
the harness stdout explicitly marks SYNTHETIC_OFFLINE_R55. These fixtures are
never claimed as native captures; the wire origin is unverified by definition.

Request context includes configured/submitted/actual dates, settings, timezone,
SDK assembly version/name/MVID and calendar metadata. Calendar fingerprints
cover the timezone's serialized rules, session definitions and holiday/partial
holiday definitions; private holiday descriptions are excluded.

The snapshot digest streams all returned rows, at most 10002. Its UTF-8 input
starts `R55_SNAPSHOT_BITS_V1|<count>\n`, then invariant decimal fields joined by
`|` and terminated by `\n`: index, timestamp ticks, numeric Kind, raw IEEE double
bits for open/high/low/close, and volume. Native timestamp Kinds and OHLCV are
observed unchanged, including Unspecified bar timestamps. No snapshot row is
exported as market data. Metadata, first/last clocks/ticks/Kinds and before/after
hashes are captured. Snapshot/calendar/request mutations prevent publication.

`RETURNED_BARS_1` and `ITERATOR_1` are run-local identity labels, not persistent
object addresses. Bars identity is enforced with ReferenceEquals against the
request's Bars and original TradingHours object. The traversal retains one
iterator local with no replacement path. Counts measure attempted operations,
including throwing constructors/calls/getters.

Every call records ordinal, source clock/ticks/Kind/derivation, source after,
inclusion flag, nullable return, bounded exception class, operation phase,
nullable bounds, guard and validity, plus trading_day and trading_day_outcome
(NOT_READ, RETURNED or EXCEPTION). Values remain null when not obtained.
Summary records false location, prior successful calls, stop flags and counts,
including trading_day_read_attempts (throwing reads count once).
`successful_calls_before_false` is zero when no false was observed; it is not
an all-true success total. Ordinals are zero-based.

Possible sealed outcomes are FALSE, REQUESTED_BOUNDARY, CALL_LIMIT,
CONSTRUCTOR_EXCEPTION, CALL_EXCEPTION and BOUND_REJECTED. None is certification.
Invalid initial inputs are rejected by the traversal before construction; the
host's valid date derivation cannot produce such an evidence contract.

An exclusive CreateNew `.json.tmp` reservation precedes submission. Publication
rechecks context and directory ownership, flushes bounded bytes, then renames
without overwrite. The seal is written/flushed to its own CreateNew temporary
file and renamed last. Evidence is capped at 262144 bytes; seal at 4096. Failed
or interrupted attempts may leave incomplete files; they are never deleted,
overwritten, retried or accepted without a valid final seal. Cleanup occurs
before publication; failed disposal prevents completion. Disposal is deferred
while submission or traversal is active.

## Independent verification and limitations

Run offline:

```powershell
py -B tools/verify_historical_utc_traversal_v1.py --capture <capture-dir>
```

The CLI calls `verify_completed_capture(capture_dir)`. It requires exactly the
two final filenames listed above in that directory, both regular files, with
no symbolic-link/reparse redirection. Ancestor directories are also checked for
redirection. Extra entries, including unrelated files or leftover temporaries,
are rejected, preserving the writer's exact-pair private-directory contract.
There is no alternate-name search, latest-file selection, promotion, repair or
deletion. Raw evidence/seal path arguments are not supported by the CLI.

A missing final artifact returns exit 1 and
`INCOMPLETE_R55_HISTORICAL_UTC_TRAVERSAL_CAPTURE`, with no PASS result. This
describes incomplete publication, not corruption. A complete pair must then
pass the byte and contract checks; successful reports add
`publication_complete=true` while keeping all authority flags false.

`validate_contract(evidence_bytes, seal_bytes)` is the separate low-level API
used by resealed contradiction tests. It validates bytes only, cannot establish
publication state and does not report `publication_complete`. In particular,
valid bytes retained in a cancelled attempt's `.done.json.tmp` can pass that
low-level check but must fail completed-capture verification.

The verifier enforces bounded input, duplicate-key rejection, exact schemas and
types, safety flags, byte/hash/run binding, date-derived coverage, calendar and
snapshot agreement, all query derivations, bounds, terminal states and exact
counter reconstruction, including trading-day outcomes and read counts. SDK
assembly metadata is split into structured fields; exactly one Version field
must match sdk_version in full. The false-query summary is independently
validated as a strict UTC timestamp (integer ticks excluding bool/float) before
comparison with the false call. Resealing inconsistent records cannot bypass those
checks. Both false and all-true observations can produce
`PASS_R55_HISTORICAL_UTC_TRAVERSAL_CONTRACT_ONLY`.

Hashes are integrity checks, not signatures. A coherently fabricated document
cannot be proven native by this verifier. It cannot recompute snapshot/calendar
digests from unavailable full native data, infer absent sessions, authenticate
SDK provenance, or establish the reason for a native false return. Pre-call
records live in bounded memory until publication; a process crash or hung native
call yields no complete observation. Stored timestamps and existing exporters
are inaccessible to the host's write path.
Completion verification assumes the private capture directory remains stable
during the read; it is not an authentication mechanism against another process
rewriting or fabricating the capture. Directory layout is checked before and
after the bounded reads.

## Offline validation and next gate

The new suite checks exact UTC values, one reused iterator, strict call/read
counts, false/exception/bound/limit stops, invalid input Kinds, property changes,
reentrancy, inline/asynchronous callbacks, termination between native operations,
snapshot/request/calendar mutation, no overwrite, independent verification and
SDK compile-only compatibility. Existing source preservation is checked against
the expected HEAD. The original eight-file 468-test R5.5-A baseline must also
pass independently and together with the new suite.

Deterministic two-thread tests pause the callback during traversal, after the
body rename, and immediately before the seal commit. A second thread publishes
termination intent while the callback still holds the state lock; events prove
intent is visible before releasing that callback. No sleeps or polling establish
the ordering. Tests assert one request/traversal, retained partial files and no
final seal or completion message. R55_OFFLINE_TESTS supplies only test checkpoint
hooks; their calls and fields are absent from the normal SDK compilation. No
production worker thread is introduced. Getter tests cover all native Kinds,
exact ticks, first/later exceptions, operation order and both boundary stops.
The cancellation tests feed their actual retained partial files to the normal
completion API and CLI and require rejection without modifying those files.
Additional completion tests cover missing, temporary, wrong-name, non-file and
extra artifacts, explicit temporary-path bypass attempts, hash/byte binding,
resealed contradictions, and valid false/all-true final pairs.

Next gate: review this offline package and its results. Any later installation
or native observation needs explicit authorization, operator-supplied dates and
output directory. Native evidence must be reviewed before proposing any
production change. This package contains no wall-clock conversion proposal.
