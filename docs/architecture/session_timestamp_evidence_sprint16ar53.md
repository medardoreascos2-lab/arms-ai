# R5.3-D — Bounded evidence writer and independent matrix verifier

Status: offline component. No NinjaTrader adapter/indicator or native experiment.
Consumes A's immutable query plan, B's matrix report and C's owner-bound lifecycle.
The earlier A/B/C sources and original probes are not modified by this package.

## Artifact and lifecycle boundary

Exactly 15 records on the complete path: EVIDENCE_STARTED, PLAN_PREPARED,
12 CASE_RESULT records and EVIDENCE_PREPARED. Results are serialized after matrix
execution; these records do NOT claim to be a real-time native call-start trace.
An interrupted or failed matrix may have only the first record and cannot seal.
Pending/failed lifecycle state, duplicate callbacks before release, close errors,
foreign directory entries and changed evidence bytes prevent publication.

C owns disposal of the writer and request. The adapter must call PublishSeal
only after C reports ReadyForSeal. The writer reads the same C instance, checks
owner identity and the exact report reference, and checks its own successful
close/hash before creating a completion seal. A shallow writer clone cannot
write, seal or close the original. Completion is not historical admission.

Use one fresh existing private directory on a fixed local drive. No reparse
points or pre-existing entries are accepted. Wrapper stdout and audit logs are
outside this directory. No deletion, overwrite, replacement or seal retry occurs.
A failed seal may leave a private .tmp file; it is not accepted as completion.
The final rename is same-directory and non-overwriting. This does not claim
crash-proof persistence on faulty hardware or hostile concurrent filesystem
mutation. The verifier checks actual bytes again after completion.

## Files and budgets

- session-timestamp-evidence.jsonl
- session-timestamp-evidence.done.json

Limits: 96 records, 262144 total evidence bytes, 32768 bytes per record,
4096 seal bytes. The current success contract requires exactly 15 records.
All files are UTF-8 without a BOM. JSONL has LF line terminators.
Raw DateTime values are encoded as unsuffixed clock text with seven fractional
digits plus integer ticks and an explicit Kind; no machine-local timezone is
inferred during serialization. Local is permitted as an observed bounds Kind.

## Verifier scope

Exact fields, types, UUID consistency, record order, complete case inventory,
plan/query/ticks/Kind consistency, variants, fixed reference controls,
source-index rules, iterator-slot graph, reuse prerequisites, charged constructor
and call attempts, bounds-read outcomes, matrix totals and lifecycle counters are
checked. Unknown fields, duplicate JSON keys, NaN/Infinity, malformed or oversized
input, missing seal, bool/float counter substitutes, and inconsistent reseals are
rejected. Every hash/byte/record count is recalculated from supplied bytes.

The verifier validates THUTC offset arithmetic; it does NOT independently
reconstruct the supplied TimeZoneInfo rules. Template/snapshot hashes identify
caller-supplied data but omitted bars/calendar payloads are not reconstructed.
Source provenance is a claim (SYNTHETIC or OPERATOR_NATIVE_RUN_UNATTESTED), never
independent attestation. A mathematically self-consistent fabricated observation
cannot be authenticated by an unsigned checksum. This is NOT a universal
anti-forgery, source-certification or provider-attribution mechanism.

A PASS_DIAGNOSTIC_CONTRACT_ONLY result always returns native provenance,
template-calendar attestation, runtime admission and execution authority as false.
Bounds validity means same-Kind positive raw tick order, not query containment.
No UTC/TradingHours timestamp interpretation is endorsed as production truth.

## Remaining adapter obligations

A later package must verify loaded request/instrument/period/lookup/merge settings,
the calendar/template and zone identity, all snapshot fingerprints and selected
source-index values, before/after calls and before preparation. It must bridge
NinjaTrader callbacks to C, adapter cursors to B, respect C checkpoints before
native operations, handle indicator clones/ownership and keep all gates disabled
by default. This writer cannot manufacture those native guarantees.

The native activation gate remains closed. No rerun of prior probes or exporter
change is authorized. R2/R4 false-return root cause remains unresolved.
