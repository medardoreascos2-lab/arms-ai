# R5.4-A — SessionIterator query-domain adapter

## Status

Offline candidate implementation only.

No NinjaTrader installation.
No native activation.
No exporter change.
No PAPER or LIVE authority.

## Component

`SessionIteratorQueryDomainAdapterV1`

The adapter receives a source `DateTime`, exact `TradingHours`, an explicit
policy, and bounded diagnostic provenance.

It never mutates the source timestamp.

## Policies

`PreserveUtc`

- accepts UTC input only
- preserves ticks exactly
- performs no conversion

`TradingHoursWallClockToUtc`

- accepts Unspecified input only
- uses the supplied TradingHours timezone
- rejects invalid wall-clock times
- rejects ambiguous wall-clock times
- explicitly derives UTC
- verifies the conversion against source ticks and the observed offset

Local DateTime input is rejected.

## R5.3 regression values

The offline harness encodes the native R5.3 reference clocks:

- A: 2026-09-15 22:01 Unspecified -> 2026-09-16 03:01 UTC
- B: 2026-09-14 21:00 Unspecified -> 2026-09-15 02:00 UTC
- C: B + one tick -> 02:00 UTC + one tick
- N: 2026-09-14 22:01 UTC remains unchanged

The same-ticks UTC relabel path remains distinct from the real timezone
conversion path.

## Fail closed

The candidate rejects:

- null TradingHours
- null timezone
- Local DateTime
- invalid DST wall clocks
- ambiguous DST wall clocks
- timezone identity/rule mutation during adaptation
- unsupported policy/input combinations
- UTC conversion range failures
- invalid provenance

No `DateTime.ToUniversalTime()` fallback is used.

No `TimeZoneInfo.Local` fallback is used.

## Mutation boundary

The source file contains no Bars/OHLCV, account, order, execution, ATM or
connection mutation logic.

The only candidate responsibility is the value passed later to
SessionIterator.

## Validation

Synthetic C# tests execute without NinjaTrader assemblies loaded.

A separate compile-only test references the installed NinjaTrader SDK.

SDK compilation is not native runtime evidence.

## Authority

`execution_authority=false`

`runtime_admission=false`

`certification_evidence=false`

`LIVE_EXECUTION=NO`

Native R5.4 confirmation remains a separate future gate.
