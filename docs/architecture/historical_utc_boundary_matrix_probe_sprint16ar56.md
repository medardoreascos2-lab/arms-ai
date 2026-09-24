# R5.6 historical UTC session boundary matrix

Status: offline diagnostic implementation. No native matrix evidence, installation,
production fix, certification, admission, or execution authorization is supplied.
The synthetic tests describe harness behavior, not NinjaTrader behavior.

## Question and established evidence

R5.5 observed one returned repository Bars object with one Bars-derived iterator:
`GetNextSession(Q0,true)` succeeded, then `GetNextSession(E.AddTicks(1),true)`
returned false. Q0 was 2026-09-14 00:00:00 UTC, ticks 639249408000000000.
The native prime end E was 2026-09-14 21:00:00 UTC, ticks 639250164000000000.
R4 also observed false at end plus one second. These observations do not establish
the internal false predicate or justify a larger-offset or timezone repair.

Reference capture: `D:\ARMS_AI_R55_CAPTURE\20260924_180319`.
Evidence SHA256: `1e8fb2d4edcc8ea21fb41b2a844dbe542c726698b96ddffde63798547949a955`.
Seal SHA256: `9948fedca50dd2d02fe365f70faed9f000b2d40eb0f377b7440204f23a2c53d1`.
These reference values are documentation only; runtime logic does not hardcode Q0
or the previously observed session bounds. Integrity verification does not
authenticate native provenance.

## Six new files

- `integrations/ninjatrader/HistoricalUtcBoundaryMatrixDiagnosticV1.cs`: bounded matrix and raw observations.
- `integrations/ninjatrader/ArmsHistoricalUtcBoundaryMatrixProbeV1.cs`: opt-in request host and final publication.
- `tools/verify_historical_utc_boundary_matrix_v1.py`: independent byte-contract and completed-capture verification.
- `backend/tests/fixtures/historical_utc_boundary_matrix_harness_sprint16ar56.cs`: synthetic SDK doubles, operation accounting, and concurrent cancellation harness.
- `backend/tests/test_historical_utc_boundary_matrix_probe_sprint16ar56.py`: behavioral, adversarial, publication, and SDK compile-only tests.
- This document.

Existing production and R5.3/R5.4/R5.5 files are unchanged. The reviewed R5.5
request, preservation, cancellation, and publication patterns are independently
implemented in the new host. No runtime dependency on the old diagnostic exists.
The identical `R55_SNAPSHOT_BITS_V1` algorithm identifier is retained deliberately
so snapshots can be compared with R5.5. It hashes count plus every row's index,
raw time ticks/Kind, exact OHLC IEEE bits, and volume. It does not convert data.

## Request and identity contract

One `BarsRequest` constructor and submission; NQ DEC26, expiry 2026-12-01,
tick size .25, point value 20, Minute/1/Last, Repository, DoNotMerge, reset=true,
dividend adjustment=false, split adjustment=false. TradingHours must be
`CME US Index Futures ETH`, timezone `Central Standard Time`.

From/Through are operator `yyyy-MM-dd` dates parsed as Unspecified, year 2026,
inclusive date parameters with an ordered span of at most 14 days. Request
FromLocal/ToLocal ticks must equal submitted date ticks; their raw Kinds are
recorded and the full request fingerprint must remain unchanged. Application
timezone must be UTC and PlaybackConnection absent.

Callback identity, returned instrument/period, Bars count 3..10002, TradingHours
name/version/timezone/rule hashes, object identity, and request preservation are
checked. SDK assembly name/version/MVID are recorded. Every SessionIterator
constructor receives the same returned repository Bars reference. Chart Bars and
the TradingHours-only constructor are never used. Run-local labels identify the
objects by construction; labels do not attest cross-run object identity.

Q0 is exactly `DateTime.SpecifyKind(from.AddDays(-2), DateTimeKind.Utc)`.
The historical lookahead limit is `SpecifyKind(through.AddDays(8), Utc)`.
Only configured dates receive these labels. Native queries, bounds, trading day,
and Bars timestamps are never relabeled or converted.

## Exact matrix

| Row | Case ID | Query | includeEndTime |
| --- | --- | --- | --- |
| A | END_INCLUDE_TRUE | E | true |
| B | END_INCLUDE_FALSE | E | false |
| C | END_PLUS_ONE_TICK_INCLUDE_TRUE | E.AddTicks(1) | true |
| D | END_PLUS_ONE_TICK_INCLUDE_FALSE | E.AddTicks(1) | false |
| E | NEXT_DAY_INTERIOR_CONTROL | Q0.AddDays(1) | true |
| F, conditional | LATER_DATE_CONTROL | Q0.AddDays(2) | true |

Order is A primed, A fresh, B primed, B fresh, and so on. Each row has its own
new pair. PRIMED_REUSED constructs a new iterator, calls Q0,true exactly once,
reads/validates the prime, then makes exactly one case call on that iterator.
FRESH_DIRECT constructs another iterator and makes only the identical case call.
E is retained as the exact DateTime returned by that row's prime end getter.

Every prime must complete with exactly matching begin/end/trading-day ticks and
Kinds. A mismatch stops immediately and disables matrix interpretation; earlier
raw observations remain recorded. No extra discovery iterator or call is needed.

F runs **if and only if neither completed E mode has classification
ADVANCING_AFTER_PRIME**. This requires true, valid UTC ordered bounds, a successful
historical trading-day read, and end greater than the agreed prime end. A false,
exception, invalid bound, terminal lookahead, same session, or earlier session is
not a usable advancing control. One usable E mode suppresses F. If the matrix
stops before both E observations complete, conditional_required remains null.
If E finishes but F is interrupted, the recorded condition remains true, but a
partial F row cannot receive the final completion seal.

Five completed rows: exactly 10 constructor attempts and 15 native calls.
Six completed rows: exactly 12 constructor attempts and 18 native calls.
Early failures have exact prefix accounting; these budgets are maxima, not
targets that permit retries. No fallback, alternative constructor, IsInSession,
IsNewSession, CalculateTradingDay, or implicit advance helper is used.

## Getters, classification, and failures

Every call records raw query clock/ticks/Kind, include flag, derivation,
source-after equality, nullable returned Boolean, phase, bounded exception class,
guard, raw getter results, and individual call/getter attempt counts. Every
iterator records case, mode, ordinal, local identity, source Bars label, whether
priming occurred, prime call and case call. Aggregate counters are independently
recomputed by the verifier.

False reads no getters. True reads begin once, end once, checks ordering, checks
the historical terminal lookahead, validates UTC, then reads trading day once.
Trading-day Kind is unconstrained and preserved. A begin beyond the historical
lookahead is REQUESTED_BOUNDARY, with no UTC normalization or trading-day read;
it is not classified as valid or used as a prime/control. This retains the
exporter's terminal-getter order. The core's initial inputs require UTC and
initial < through; non-UTC inputs never reach a constructor.

Case comparisons deliberately do not impose the exporter's strictly increasing
prior-end guard: observing the same or an earlier valid session is the question
being tested. Successful cases are classified from raw bounds:

- SAME_AS_PRIME: begin and end exactly match prime ticks and Kinds.
- ADVANCING_AFTER_PRIME: valid completed observation with end > prime end.
- OTHER_VALID_SESSION: other valid completed bounds.
- RETURNED_FALSE: false, no getters.
- EXCEPTION: native call/getter threw; no retry or further getter on that iterator.
- BOUND_REJECTED: order/Kind guard failed.
- REQUESTED_BOUNDARY: historical terminal lookahead, no further interpretation.

ADVANCING_AFTER_PRIME does not assert adjacency, containment of the query, or
that this is the immediately following session. The interior-control name is a
hypothesis; raw bounds must establish actual containment if it matters later.

Case failures end only that iterator observation; independent peers still run.
A failed prime, prime disagreement, constructor failure, or query arithmetic
overflow stops the whole matrix with interpretation_allowed=false. The reviewed
A-E aborted-prefix contract is unchanged while conditional_required is null.
Once conditional_required is known, final publication requires exactly the
complete A-E matrix (false) or the complete A-E matrix plus both F modes (true).
AddTicks/AddDays
overflow is recorded as ArgumentException at DERIVATION before any case call.
No wrapping or larger-offset retry is permitted. Input rejection occurs before
native work and is exercised directly offline; the host supplies validated dates.

### Conditional-F structural completion

F is atomic for publication, not native success. Each mode must have its actual
case-observation object. A constructor-only or prime-only entry does not count,
even if its mode label and bounded exception have been recorded. In particular,
a FRESH_DIRECT constructor exception after a valid PRIMED_REUSED observation
leaves F incomplete. A false case result, bounded GetNextSession/getter exception,
or recorded case guard failure does count as an observation; it does not have to
be an advancing or successful native result. Successful priming remains required
before the primed case call. No missing mode is synthesized or retried.

The host independently checks exact row/mode order, non-null case observations,
completed entry phases, completed matrix outcome, and 10/15 or 12/18 constructor/
call accounting before creating the seal file and again at the seal commit gate.
An ordinary partial F abort retains its bounded body JSON without any final or
temporary seal. Cancellation may leave only the reserved temporary body, as
before. No retained artifact is deleted. Low-level byte validation may inspect
consistent aborted prefixes, but completed-capture verification independently
rejects partial F even with an internally consistent, correctly hashed seal.

## Lifecycle, preservation, and publication

All activation controls default false/empty. One DataLoaded opportunity is
consumed even when disabled. Editing properties cannot rearm. Reentrant/duplicate
callbacks cannot enter the matrix twice. A clone cannot terminate its owner.
The single request is disposed once before publishing a completion seal.

Termination first acquires the narrow sealPublication gate and publishes an
Interlocked cancellation intent, then releases that gate before waiting for the
ordinary callback/state lock. The final seal rename uses the same narrow gate
and rechecks cancellation. Earlier cancellation prevents completion; a completed
rename preceding cancellation is already committed. No broad traversal/write
work holds this gate. Conditional test checkpoints are absent from SDK builds.

The host requires a fresh, pre-existing, empty private directory on a fixed local
drive, with no reparse ancestor. It reserves a create-new body temporary file,
writes bounded UTF-8 JSON with write-through and Flush(true), renames the body,
writes/flushes a create-new temporary seal only after the structural completion
gate passes, then rechecks structural eligibility and commits the final seal. No
overwrite, deletion, repair, alternative filename, or retry occurs. Interrupted
files remain for operator inspection.

Final pair:

- `historical-utc-boundary-matrix.json`, at most 262144 bytes.
- `historical-utc-boundary-matrix.done.json`, at most 4096 bytes.

The seal binds body bytes, SHA256 and run ID. Both artifacts label DIAGNOSTIC_ONLY
and OPERATOR_NATIVE_RUN_UNATTESTED. Native provenance, certification, admission,
execution authority, exporter invocation/change, stored timestamp mutation,
Bars/TradingHours mutation, PAPER and LIVE flags are all false.

`validate_contract(raw, seal_raw)` validates only supplied bytes, including
consistent partial diagnostic data. It never reports publication_complete or
establishes eligibility to publish. `verify_completed_capture(directory)` also
requires structural completion of the conditional row and exactly the regular
non-reparse final pair, then rechecks directory layout. The CLI
accepts only `--capture DIRECTORY`. A temporary seal cannot substitute for a final
seal. Missing final artifacts and consistent but structurally incomplete F
captures report INCOMPLETE; other invalid captures fail.
False, mixed, all-true, and consistent native exceptions can pass the contract.
No particular native outcome is required and no production strategy is selected.

Private-directory stability and operator isolation remain prerequisites. These
checks do not authenticate native provenance or defeat a concurrent hostile
writer. Before/after snapshots detect net changes, not transient mutate/restore
activity. All SDK interaction here is read-only apart from constructing/submitting
the one explicitly scoped repository data request; there is no connection mutation,
account, order, execution, ATM, exporter, or stored-data writer surface.

## Offline validation and next gate

Run the new test file with `py -B -m pytest -q -p no:cacheprovider`, then the nine
prior baseline files, then all ten together. The harness asserts query ticks,
flags, isolated object lifetimes and getter order independently of the emitted
evidence. It covers prime failures/disagreement, conditional budgets, case
exceptions, arithmetic overflow, all native Kinds, preservation failures, one-shot
callback behavior, concurrent cancellation, overwrite refusal, strict publication,
resealed contradictions, and authority exclusions. A separate compile-only test
references installed NinjaTrader assemblies; it never loads their runtime.

Focused partial-F regression scenarios include the exact review finding (only
PRIMED_REUSED, constructor exception, 11 constructors/15 calls), prime false,
prime/case/getter exceptions, prime order/Kind guards, prime disagreement, a fresh
constructor failure, cancellation preventing the second mode, and F date overflow.
The retained-body tests forge a correctly bound final seal in a separate test
directory and require the completed-capture API and CLI to reject it. Additional
tests reject missing, duplicate, extra, and incomplete F mode records, and accept
both real case records with false or bounded exception outcomes. These fixtures
are synthetic offline evidence only.

Next gate: independent adversarial review of these six uncommitted files and the
offline test results. Installation and native execution require a later explicit
authorization. Any later capture must compare its request and snapshot identity
with R5.5 before cross-run conclusions. Root cause remains unproven until native
matrix observations exist; even then sensitivity comparisons are descriptive,
not causal proof or authorization to modify production traversal.
