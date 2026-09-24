# R5.4-B — native query-domain comparison core

## Status

Offline candidate only.

No NinjaTrader installation.
No native activation.
No exporter changes.
No PAPER or LIVE authority.

## Purpose

This package composes the committed R5.4-A adapter with the same native
`SessionIterator(Bars)` / `GetNextSession(query, true)` API surface already
exercised by R5.3.

The comparison contains exactly three isolated iterator cases:

1. `C_RAW`
   - original Unspecified clock
   - original ticks

2. `C_SAME_TICKS`
   - identical ticks
   - DateTimeKind changed to UTC only

3. `C_ADAPTER`
   - original source passed to `SessionIteratorQueryDomainAdapterV1`
   - TradingHours wall-clock interpretation
   - explicit UTC query

Each case receives its own `SessionIterator`.

No retry exists.

Maximum iterator constructors: 3.

Maximum GetNextSession attempts: 3.

## Preservation

The source DateTime ticks and Kind are captured before the comparison and
verified unchanged afterward.

The R5.4-A adapter retains its own source-preservation checks.

The comparison core does not alter Bars, TradingHours, OHLCV, historical
files, application timezone or connection state.

## Bounds

`ActualSessionBegin` and `ActualSessionEnd` are read only when
`GetNextSession` returns true.

A returned session is accepted diagnostically only when end > begin.

No bounds are read after a false result.

## Checkpoints

A caller-supplied checkpoint is invoked before:

- each SessionIterator constructor
- each GetNextSession call
- each readable session-bound access

A future native host can bind those checkpoints to its existing
environment/context validation.

## Offline evidence

The synthetic harness models the observed R5.3 C distinction:

- RAW -> false
- SAME_TICKS -> false
- ADAPTER -> true

The synthetic result is not native evidence.

A separate compile-only test references the installed NinjaTrader SDK.

SDK compilation is also not native runtime evidence.

## Safety

The core contains no:

- account API
- order API
- execution API
- ATM API
- connection mutation
- file writer
- retry loop
- exporter mutation

`execution_authority=false`

`runtime_admission=false`

`certification_evidence=false`

`LIVE_EXECUTION=NO`

## Next gate

After offline review and a separate commit, a later diagnostic Indicator may
host this core, persist bounded evidence, and perform one explicitly authorized
native comparison.

That later native run must use a fresh private output directory and must not
upgrade trading or historical-data authority.
