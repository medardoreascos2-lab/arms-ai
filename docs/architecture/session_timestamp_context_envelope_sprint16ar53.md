# R5.3-G — Bind loaded context to the sealed matrix

Status: offline implementation; native Indicator and activation are NOT included.
The package's tests must pass on the operator's Windows environment before any
promotion. Synthetic results do not resolve R2/R4 GetNextSession false returns.

## Unchanged inputs

A plan, B executor, C resource lifecycle, D matrix writer/verifier, E SDK bridge,
and F1 loaded request/snapshot context remain byte-identical. G is additive.
The F1 context source still matches F; the prior failed F audit is preserved.
The earlier R5.2 capture describes a different observed snapshot and is never
reused as this package's output. No fixed 4503/5520 row-count assumption is made.

## New composition

`SessionTimestampContextEnvelopeV1` implements IDisposable for C's writer factory.
It receives the same owner, C lifecycle and F context. It is NOT an Indicator and
has no request submission, native cursor call, chart interaction or order access.
During Prepare it validates the F context while the request is still owned,
binds every plan control by reference to that context, writes F's exact captured
UTF-8 bytes, calls D.Prepare and revalidates the snapshot. C's final checkpoints
still run. C/E close the request exactly once and dispose this wrapper, which
closes D's writer exactly once. No success seal is published during Prepare.

After resource release, PublishSeal checks C readiness/identity and current
operator/timezone/Playback gates using F.CheckEnvironment only. It NEVER reads
Bars after the request has been disposed. It verifies the saved context hash,
asks D to publish its own seal, then binds that seal, D's JSONL and the context
in a distinct final envelope. It holds read handles denying writes/deletes to
those files while checking their bytes and publishing the envelope.

An invalid owner or shallow clone cannot prepare, publish or close the original.
Repeated publication is rejected, not repeated. No writer overwrites or deletes
existing evidence. Creation is restricted to an existing empty fixed-local path
with reparse-point checks. Failures can leave incomplete files for inspection.

## Capture layout and completeness

```
capture/
  session-timestamp-context.json
  matrix/
    session-timestamp-evidence.jsonl
    session-timestamp-evidence.done.json
  session-timestamp-context.done.json
```

D's child seal alone is NOT a complete G capture. A failure after publication of
D's seal may leave that child pair intact without a G envelope. The G CLI requires
all four files and rejects foreign entries. Logs/stdout and audit reports stay
outside capture. Nothing is placed in the old R5.2 output directory.

The final envelope binds three files with exact relative names, SHA256 and byte
counts; it binds probe/request UUIDs and origin to D, snapshot/calendar digests,
row count, source index/timestamp and observed iterator/call budgets. The envelope
itself has no cryptographic signature and makes no authenticity claim.

## Boundaries and limits

- One request (created by F, submitted through C/E), at most 12 GetNextSession
  attempts and 11 constructor attempts (unchanged A/B/E contracts).
- 15 D matrix JSONL records. D's 32768-byte per-record bound remains unchanged.
- One separately bounded captured-context JSON document: maximum 131072 bytes.
  This is a sidecar, not a per-bar JSONL record.
- D's seal and G's seal: maximum 4096 bytes each.
- All four persisted files combined: maximum 262144 bytes.
- No per-bar logging, history admission, repair or execution authority.

## Independent Python verification

`verify_session_timestamp_context_envelope_v1.py` first verifies manifest hashes,
byte limits, file layout and exact scalar types. It invokes the unchanged D
verifier for the full matrix/lifecycle contract, then validates the F schema,
request dates/policies, snapshot aggregate invariants, source-index binding,
calendar fields and reference observations. It rejects duplicate keys, JSON
NaN/Infinity, extra/missing fields, bool/float substitutions for integers,
contradictory source/plan/hash links, relevant calendar exceptions and invalid
or incomplete seals. Actual FromLocal/ToLocal Kinds are recorded, not silently
relabelled. Numeric tick size and point value remain numbers, not booleans.

Every timestamp's text, ticks and Kind are cross-checked. B/C/R/N keep their
reference provenance; an out-of-range reference is not declared a native bar.
A is bound to the first captured native timestamp by F and to that same observation
in the offline context/matrix graph. The complete bar array is not persisted;
its fingerprint cannot be independently reconstructed by G's verifier.

The .NET `TimeZoneInfo.ToSerializedString()` blob is bound as exact text plus
hash. G's Python verifier does NOT deserialize .NET zone rules or independently
re-evaluate DST for every query. It checks the saved reference clock/UTC/offset
relationships and D checks THUTC algebra. This limitation is returned explicitly
as `zone_rules_independently_reevaluated=false`; the zone blob is not provider
attestation and not proof that a timestamp's Unspecified Kind denotes UTC or
Chicago time. F/A perform the runtime ambiguity/range checks on the loaded zone.

SHA256 and a self-consistent envelope do not defeat an attacker who can coherently
replace all files and recompute all hashes. `native_provenance_attested=false`,
`operator_observations_independently_verified=false`, `certification_evidence=false`,
`runtime_admission=false` and `execution_authority=false` remain mandatory.
Filesystem observations are bounded checks, not a universal adversarial TOCTOU
or power-loss-atomicity guarantee. The host/SDK source identity is not attested
merely by reading a recorded MVID.

## G1: exact aggregate Kind transition feasibility

The offline verifier now requires that **some** sequence has the reported three
Kind counts, first/last Kinds and exact number of adjacent changes. Scalar checks,
the 3..10002 row bound and first-bar `Unspecified` requirement remain unchanged.
The mathematical helper is also tested at lengths 1 and 2; those lengths are
not admitted by the context contract. No C# or native behavior changes.

Let `R = transitions + 1` be the number of maximal constant-Kind runs. For Kind
`i`, let `c_i` be its row count, `r_i` its run count, and `e_i` the number of
fixed endpoints of that Kind (0, 1 or 2). If R=1, both endpoints must be the
single present Kind. Otherwise each present Kind needs at least one run, each
absent Kind zero runs, and equal endpoints need two separate runs. Thus:

```
lo_i = max(1 if c_i > 0 else 0, e_i)
hi_i = min(c_i, floor((R - 1 + e_i) / 2))
```

The exact criterion is `lo_i <= hi_i` for every Kind and
`sum(lo_i) <= R <= sum(hi_i)`. Integer intervals have no gaps in their possible
sums, so this selects run counts summing to R without enumerating them. The
verifier uses three iterations, constant auxiliary space and no row expansion.

Necessity: any run ordering gives a loopless undirected multigraph with Kinds
as vertices and its R-1 adjacent transitions as edges. Vertex i has degree
`d_i = 2*r_i - e_i`; no vertex can have degree greater than R-1. Together with
`r_i <= c_i`, this yields exactly the upper bounds above and the stated lower
bounds. The ordering therefore satisfies the criterion.

Sufficiency for exactly three available Kinds: choose run counts from those
intervals with total R. The degrees are nonnegative, sum to `2*(R-1)`, and each
is at most half the total. For three vertices, the edge multiplicity between
i and j is `(d_i + d_j - d_k)/2`. These are nonnegative integers: the bounds
give the triangle inequalities and the degree sum is even. A missing vertex
has degree zero; the same formulas cover two used Kinds. Every used vertex
has positive degree when R>1, including the equal-endpoint vertex whose lower
bound is two runs. A loopless graph on at most three positive-degree vertices
is connected, since disconnected nonempty components would each need at least
two vertices. With different endpoints, exactly those two vertices have odd
degree; with equal endpoints all degrees are even. An Euler trail (or circuit
started at the specified endpoint) therefore produces a run ordering with
the required endpoints, no identical adjacent Kinds and exactly r_i runs of
each Kind. Expand each run to at least one row, distributing the remaining
`c_i-r_i` rows within its runs. This preserves the endpoints and transitions
and proves existence. The single-used-Kind case with R>1 cannot satisfy the
interval sum and is rejected. This proof relies on at most three Kinds.

The regression includes the reported 4 Unspecified / 1 Local summary: two
transitions are feasible with Unspecified endpoints, four are impossible.
It also checks two-Kind alternation, three-Kind mixtures, singleton/minority
Kinds, different endpoints and the maximum row count. All envelope cases
rebuild dependent byte counts and SHA256 seals and verify the unchanged inner
matrix contract before checking the aggregate. An independent oracle directly
enumerates all three-Kind sequences of lengths 1..8 and compares possible and
impossible count/endpoint/transition combinations. A private negative control
removes only the new feasibility call and must fail the reported regression.

This checks combinatorial possibility only. It does not reconstruct omitted
bars, establish a unique or actually observed ordering, attest native provenance,
interpret Unspecified, resolve GetNextSession=false, or authorize exporter or
trading changes. Existing attestation and authority flags remain false.

## Tests and installation boundary

G compiles against installed SDK references without executing that library.
The runnable harness instead compiles A-F1/G plus F1's explicit SDK doubles;
`/main:ContextEnvelopeHarness` selects G's entry point. No actual NinjaTrader
assembly is loaded by that executable. C# cases exercise success/failure results,
normal/inline/async callbacks, irrelevant calendar exceptions, mixed Kinds,
4503/5520/10002 rows, mutations, early sealing, clones, ownership, existing files,
late callbacks and disposal failures. Private Python checks and pytest test the
verifier with independently constructed five-row reference data and resealed
contradictions. Actual emitted C# samples must also pass the Python verifier.

No commit/push, source overwrite, prior-capture deletion, SDK configuration
mutation or native activation is performed. The full NinjaScript host and its
installation/activation procedure remain a later separately reviewed step.

## Primary reference consulted

Microsoft describes ToSerializedString and FromSerializedString as the pair for
persisting/restoring zone rules; G deliberately does not substitute the verifier
machine's current time zone or registry rules for the captured blob.
https://learn.microsoft.com/en-us/dotnet/standard/datetime/saving-and-restoring-time-zones
