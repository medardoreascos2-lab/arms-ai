# R5.4-C — native repair confirmation host

## Status

Offline host/evidence implementation only.

Not installed.
Not activated.
No native run.
No exporter change.
No PAPER or LIVE authority.

## Purpose

`ArmsSessionIteratorQueryDomainRepairProbeV1` hosts the committed R5.4-A
adapter and R5.4-B three-way native comparison.

The intended one-shot native comparison is:

- C_RAW
- C_SAME_TICKS
- C_ADAPTER

The source is the R5.3 C reference clock:

`2026-09-14T21:00:00.0000001`, `DateTimeKind.Unspecified`.

## Chart contract

The host requires:

- NQ DEC26
- Minute / 1
- MarketDataType.Last
- CME US Index Futures ETH
- Central Standard Time

The chart Bars object identity must remain unchanged during the diagnostic.

## Operator gates

Five properties exist:

- Probe enabled
- Fresh private output directory
- Operator confirms market reopened
- Operator confirms NQ data flow
- Operator confirms stable connection

All default to disabled/empty.

The instance gets one DataLoaded initialization opportunity and cannot be
rearmed by repeatedly changing properties.

## Query boundary

The host does not perform timezone conversion itself.

It invokes `SessionIteratorQueryDomainNativeComparisonV1`, which delegates the
candidate query conversion exclusively to
`SessionIteratorQueryDomainAdapterV1`.

The source clock is compared before and after and must remain unchanged.

## Evidence

A successful attempt creates exactly two new files in a pre-existing empty,
local, fixed-drive, non-reparse output directory:

- `session-query-domain-repair.json`
- `session-query-domain-repair.done.json`

No overwrite or deletion is permitted.

The evidence records:

- source before/after
- source preservation
- adapter source/query ticks and Kinds
- TradingHours zone identity/fingerprint
- C_RAW outcome
- C_SAME_TICKS outcome
- C_ADAPTER outcome
- readable valid bounds when a call returns true
- exact constructor/call budgets
- whether the R5.3 expected pattern was reproduced

## Expected native pattern

The target diagnostic observation is:

- C_RAW -> false
- C_SAME_TICKS -> false
- C_ADAPTER -> true with valid bounds

A different observation remains diagnostic divergence and does not authorize a
repair.

## Limits

Exactly three SessionIterator constructors and three GetNextSession calls are
allowed by R5.4-B.

There are no retries.

## Verifier

`verify_session_iterator_query_domain_repair_v1.py` validates file layout,
byte hash, source preservation, case order, query-domain distinction, budgets,
authority flags and the computed expected-pattern flag.

The verifier does not attest native provenance.

## Authority

Always false:

- native_provenance_attested
- certification_evidence
- runtime_admission
- execution_authority

The host does not mutate:

- exporter behavior
- stored timestamps
- accounts
- orders
- ATM
- connections
- strategy execution

`LIVE_EXECUTION=NO`

## Next gate

After offline tests and local commit, installation requires a separate reviewed
copy into the existing NinjaTrader library.

A native run then requires a fresh empty output directory and explicit current
operator confirmations.

No production integration is authorized by R5.4-C.
