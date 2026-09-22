# Sprint 16A-R5.1: coverage failure forensics

Offline diagnostic hardening only. No native rerun, installation, historical repair,
admission change, execution authority, commit or push is authorized by this phase.
Baseline HEAD: `1f94bf879e585421be0c8c2d09e56e75b6b73784`.

## Established evidence and limits

R5 run `3c1dafe2-f31f-4d60-80b8-3961fbf36d8d`, probe
`83bd283e-7a26-4ab3-97b0-a0dd60db0886`, request/snapshot
`0fa7454c-ab55-4246-a256-fd86aea2ca69` persisted five records, 12,967 bytes.
JSONL SHA256: `3768a821cef711a7384eedfb480930ba9520582d5536fd298cd4f4790bc0072c`.
It ends with `ATTEMPT_FAILED`, operation `COVERAGE`, `InvalidOperationException`;
4,503 returned rows, zero iterator constructions and zero GetNextSession calls.
There is no seal. The committed success verifier rejects it. These are unsealed
observations, not independently authenticated native provenance.

`Completed` checks callback identity/error, calls `ValidateSnapshot` (environment,
instrument/period/request/template/version/schedule and count), stores Count,
fingerprints timestamps/Kinds/OHLCV, and writes `SNAPSHOT_VERIFIED`. Only then does
it assign `stage=COVERAGE` and call `Measure`. `COVERAGE_VERIFIED` is after Measure
returns. The persisted failure is therefore within Measure or the subsequent
coverage trace write, not within ValidateSnapshot or a SessionIterator call.
**The old trace cannot even exclude a failure constructing/writing
COVERAGE_VERIFIED after a successful Measure**, because stage remains COVERAGE
and the coverage field is omitted from ATTEMPT_FAILED. No exact invariant is
retrospectively recoverable. Snapshot fingerprint equality with R4 does not
recover omitted labels or their Kinds.

## Ordered audit of committed Measure (baseline lines 311-355)

This list follows evaluation order; branches repeat per bar/session. The actual
first failing site is unknown. Explicit Require calls throw InvalidOperationException;
opaque SDK getters are potential indirect sources, not proven exception contracts.

1. Allocate six Bucket objects, SortedDictionary with Ordinal comparer, post Bucket,
   four gap Buckets, boundary List. Ordinary constructors/allocation can fail (e.g.
   resource exhaustion), but are not a normal InvalidOperationException source.
2. Read `bars.GetTime(0)` for first. SDK access can throw; bounds are based on the
   earlier count and are not independently rechecked here.
3. Read `bars.GetTime(returnedRows-1)` for last: same opaque SDK risk.
4. Per increasing index, read `bars.GetTime(i)`: same opaque SDK risk.
5. First compound Require operand: `time.Kind == Utc`. False throws
   InvalidOperationException; later operands are short-circuited.
6. Second operand: `time > previous`, initially MinValue. False throws the same
   exception, including equality/duplicates; comparison itself does not throw
   because Kinds differ.
7. Third operand: `time.Ticks % TicksPerMinute == 0`. False throws the same
   exception. Ticks and fixed nonzero modulo are not independent exception sites.
8. Assign previous, format invariant `yyyy-MM-dd`, dictionary ContainsKey. Known
   valid format, nonnull generated key and Ordinal comparer have no expected
   InvalidOperationException path here. For a new day, Require `dates.Count < 32`
   explicitly throws; Add may throw ArgumentException for duplicate keys or fail
   allocation, but this local dictionary is not shared/concurrently enumerated.
9. Date Bucket.Add and optional post Bucket.Add: increment count, store indices,
   call Stamp for first/last. Stamp uses nullable DateTime and invariant `o` format.
   There is no explicit InvalidOperationException; ordinary valid DateTime
   formatting and integer assignments have no expected such path. Counters are
   bounded by 10,002, far below overflow.
10. For each of six fixed SessionOffsets (0,1,2,3,4,7), calculate begin/end using
    AddDays on September 2026 anchors. AddDays can throw ArgumentOutOfRangeException
    generally, but these fixed arguments are valid. Array indices are 0..5.
11. Compare exact boundaries; append an anonymous index/Stamp object to List.
    List growth can fail allocation, not ordinarily InvalidOperationException.
    With strictly increasing timestamps and 12 distinct fixed endpoints, at most
    12 boundary observations can be added. No list enumeration occurs here.
12. Test `(begin,end]`; update session Bucket, candidate index/Stamp and earliest
    covered query. Same bounded storage/Stamp semantics as step 9, no native API.
13. For j<4, calculate end.AddHours(1), compare maintenance membership and update
    gap Bucket. Fixed valid dates cannot overflow; same Stamp/storage semantics.
14. Increment maintenance/outside counters where applicable; no expected exception.
15. Read `bars.Count` through SDK; then Require equality with returnedRows. Getter
    failure is opaque; a changed count explicitly throws InvalidOperationException.
16. Read bins[1].count; construct summary using Stamp(first/last/coveredQuery),
    Kind.ToString and existing collection references. Valid formatting has no
    expected InvalidOperationException path; allocation failures remain possible.

After Measure: `Trace(COVERAGE_VERIFIED)` checks writer/record budget, serializes
coverage, checks 16-KiB row / 256-KiB total budgets, and writes. Its Require guards
also throw InvalidOperationException under the same old COVERAGE operation.
Serialization and writer/stream operations can also fail. R5.1's independent
COVERAGE_COMPLETE checkpoint distinguishes completed measurement from a later
main-trace failure without making that failure successful evidence.

## Timestamp and index contracts

**Public .NET evidence:** [Microsoft Framework DateTime source](https://github.com/microsoft/referencesource/blob/main/mscorlib/system/datetime.cs)
implements greater-than with InternalTicks and stores Kind separately.
[Microsoft GreaterThan documentation](https://learn.microsoft.com/en-us/dotnet/api/system.datetime.op_greaterthan)
describes tick comparison. No implicit timezone conversion or exception is caused
by Utc versus Unspecified. A 2026 Utc timestamp is greater than MinValue. A Utc
timestamp with zero ticks would fail equality, independently of Kind. A compiled
test on this machine's .NET Framework verifies these cases. No relabeling/change
to initialization is made.

**Public NinjaTrader evidence:** [GetTime](https://ninjatrader.com/support/helpguides/nt8/gettime.htm)
uses an absolute bar index, distinct from bars-ago indexing. The
[BarsRequest example](https://ninjatrader.com/support/helpguides/nt8/barsrequest.htm)
walks indices 0 through Count-1. [How Bars are Built](https://ninjatrader.com/support/helpguides/nt8/how_bars_are_built.htm)
describes close-time labels and gives a minute-aligned example. These reviewed
pages do not establish a universal zero-subminute-ticks guarantee for every
repository BarsRequest snapshot, nor guarantee strict uniqueness of every
returned absolute-index timestamp. Do not apply reverse bars-ago indexing here.

**Installed implementation evidence:** SDK assembly identity is 8.1.8.2. Read-only
review of `bin/Custom/BarsTypes/@MinuteBarsType.cs` (SHA256
`64f0d2960217dc9ae23bd29f7d0a1c62e3bb22fb5909e0608e1ef53e83461bd4`)
shows Count-1 used for lastBarTime, appending later labels and updating existing
bars for earlier/equal input. With reset enabled it calculates integral-minute
offsets from ActualSessionBegin and clips to ActualSessionEnd. That supports
oldest-to-newest absolute traversal and minute alignment when native boundaries
are aligned; it is not a universal repository-data guarantee. No SDK internals
were executed to create a request and no NinjaTrader process was manipulated.

**R2/R4/R5 native evidence:** iterator session bounds are not bar-label bounds.
R2 failed before exporting labels; R4 fingerprints labels without exposing them;
R5 failed without coverage context. None identifies the first bad bar or proves
alignment/strict ordering of all 4,503 timestamps.

**Inference:** ascending absolute traversal is supported by public API usage and
installed code; strict increase and minute alignment remain defensive checks on
this snapshot, not retrospectively verified facts. Neither traversal nor guard
has been changed. Original failure and GetNextSession root cause remain unresolved.

## Minimal diagnostic change and bounds

The primary v1 JSONL, seal and verifier contract are unchanged. A separate
`session-domain-coverage.jsonl` is created exclusively during Measure with
WriteThrough/AutoFlush. It uses `arms.nt.session-domain-coverage.record.v1`, revision
R5.1/1, FORENSIC_ONLY, runtime_admission=false, certification_evidence=false. It
binds probe/request UUID and the recorded snapshot hash. It has no success seal
and is not covered by the primary seal. Readability is not integrity verification
or authentication; modifications to this sidecar cannot establish a valid matrix.
No alternate PASS-producing parser is introduced: ordinary bounded JSON parsing
is sufficient for these forensic rows.

Records: BEGIN, FIRST_OBSERVED, LAST_OBSERVED, checkpoints after processing index
0 and every 1,024 indices thereafter, then COMPLETE or immediate GUARD_FAILED.
At most 10 checkpoints for 10,002 bars: 14 normal rows, at most 15 if a final write
failure leaves room for a failure row. Hard sidecar ceilings: 16 rows, 2,048 bytes
per row, 32,768 bytes total. Main and sidecar together enforce the original
96-row / 262,144-byte ceilings, with no per-bar record stream. Existing successful
main evidence is at most 22 rows (including eight calls); normal combined count
is at most 36. Primary seal counts/hash still refer only to primary JSONL.

Context includes iteration, expected/observed count, first/last/current/previous
timestamp and original Kind, last successfully processed index/time/Kind,
seconds/milliseconds/subsecond and subminute tick remainders, UTC date only when
Kind is already Utc, date bucket count, current session bin/classification and
operation. Current is cleared before each SDK read, so a failed getter cannot
misrepresent a stale timestamp as its result. Classification remains
NOT_CLASSIFIED until available. Previous starts at unchanged MinValue.

Explicit guards: COVERAGE_KIND_NOT_UTC, COVERAGE_NON_INCREASING,
COVERAGE_NOT_MINUTE_ALIGNED, COVERAGE_DATE_BUCKET_LIMIT,
COVERAGE_FINAL_COUNT_CHANGED. Failed getters identify COVERAGE_GET_FIRST_FAILED,
COVERAGE_GET_LAST_FAILED, COVERAGE_GET_TIME_FAILED or
COVERAGE_FINAL_COUNT_READ_FAILED. Other exceptions use the last explicit
operation plus _FAILED. All exception types pass the existing allowlist; messages
and stack traces are never emitted. The first failing short-circuit invariant
is reported; later invariants are not inferred.

Exceptions still propagate to the existing fail-closed lifecycle: no matrix after
coverage failure, no completed evidence seal, request disposal, no retries. Writer
or storage failure can itself prevent the final diagnostic write; persistence is
best effort under disk/budget failure and must never be claimed guaranteed.
Output ownership now allows exactly the primary JSONL and the exclusively created
sidecar before sealing. Unexpected files still prevent sealing.

`FORENSIC_TRACE_READABLE=YES` describes parseable JSON only.
`OFFLINE_VERIFIER_STATUS=REJECTED` remains required for unsealed failed attempts.
The old five-record R5 trace remains unchanged and cannot gain missing context.

## Validation and proposed scope

Synthetic harness fault injection occurs after fingerprinting for first/last/loop
getter failures and count mutation. Tests cover Unspecified/Local Kind, reversed
order, duplicates, seconds and 100-ns misalignment, 33rd date, count mutation,
first/last/current getter exceptions, exact failure context, no iterator calls or
seal, and 4,503 / 10,002-row success with bounded progress and normal verification.
Existing R5 tests are retained unchanged, including corruption rejection,
structural safety, lifecycle behavior and compilation against installed SDK DLLs.

Final offline validation: 222 focused tests passed (207 existing R5 plus 15 R5.1);
2,108 regression tests passed, including those 222 (not additive). Zero failures,
errors or skips. Installed SDK 8.1.8.2 compilation passed. The regression command
extends the prior 1,886-test suite with R5 and R5.1, covering Sprint15Z, 16A/R1-R5,
session/calendar, market data and MVP safety under the preserved repository test
policy environment. Exact commands/environment and JUnit results are in the
private offline directory. Two existing warnings concern a Starlette deprecation
and pytest JUnit record_property formatting; neither is a test failure.

Measured synthetic combined evidence: 4,503 rows -> 31 records / about 54 KB;
10,002 rows -> 36 records / about 61 KB. These are synthetic diagnostics only.
Preservation checks cover 109 unrelated untracked files and 2,625 baseline private
artifacts, prior commits, protected components, and byte hashes of R4/failed R5.

Proposed commit scope only:

- integrations/ninjatrader/ArmsSessionDomainProbeV1.cs
- backend/tests/fixtures/session_domain_probe_harness_sprint16ar5.cs
- backend/tests/test_session_domain_coverage_sprint16ar51.py
- docs/architecture/session_domain_coverage_sprint16ar51.md

Private offline test logs/manifests live under `.arms-dev/sprint16a-r51/offline`;
they are excluded from commit scope. Prior captures and manifests are preserved.
No installation or new native capture directory is prepared. Next step is human
review of this diff; commit, installation and a native rerun require separate
authorization. No historical behavioral repair is justified by this change.
