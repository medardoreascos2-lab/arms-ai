# ARMS AI — Sprint 16A-R5.2 Timestamp Domain Probe

## Status

Design only.

No native R5.2 execution has occurred.

## Established native evidence

R5.1 returned 4,503 NQ DEC26 Minute/1 repository bars.

The R5.1 forensic sidecar established:

- first returned timestamp:
  `2026-09-15T22:01:00.0000000`
- first DateTime.Kind:
  `Unspecified`
- last returned timestamp:
  `2026-09-21T04:03:00.0000000Z`
- last DateTime.Kind:
  `Utc`
- R5.1 failed closed at index 0 on:
  `COVERAGE_KIND_NOT_UTC`
- SessionIterator calls executed:
  `0`

This proves the R5.1 coverage failure.

It does not establish why GetNextSession returned false in R2/R4.

## Purpose

Create a new isolated diagnostic component:

`ArmsTimestampDomainProbeV1`

Its only purpose is to characterize the timestamp domain returned by one
repository-only BarsRequest.

It must not reinterpret, normalize, convert, or repair timestamps.

## Native scope

Exactly one BarsRequest.

Target:

- instrument: NQ DEC26
- bars: Minute / 1
- market data: Last
- trading hours: CME US Index Futures ETH
- lookup: Repository
- merge: DoNotMerge
- requested interval: 2026-09-16 through 2026-09-21
- application timezone gate: UTC
- Playback: prohibited

## Prohibited behavior

The probe must contain:

- zero SessionIterator calls
- zero account API access
- zero order API access
- zero ATM API access
- zero execution authority
- zero connection mutation
- zero historical exporter mutation
- zero production exporter mutation
- zero FreshNativeAdapter mutation

## Timestamp observations

For every returned bar, inspect the raw DateTime returned by `Bars.GetTime(i)`.

Do not call:

- ToUniversalTime()
- ToLocalTime()
- SpecifyKind()
- TimeZoneInfo.ConvertTime*
- DateTimeOffset conversion as a normalization mechanism

Record aggregate counts:

- total rows
- DateTimeKind.Utc count
- DateTimeKind.Unspecified count
- DateTimeKind.Local count

Record first and last index for each Kind.

## Kind transitions

Detect every adjacent change in DateTime.Kind.

For each transition record:

- transition ordinal
- current index
- previous index
- previous timestamp
- previous Kind
- current timestamp
- current Kind
- raw previous ticks
- raw current ticks
- raw tick delta

Maximum persisted transitions: 16.

If more than 16 transitions occur:

fail closed with a bounded diagnostic.

## Raw ordering observations

Using raw DateTime.Ticks only, count:

- strictly increasing adjacent pairs
- duplicate adjacent timestamps
- decreasing adjacent timestamps

Do not interpret these counts as timezone-normalized ordering.

Record first index/context for:

- duplicate
- decrease

## Minute alignment observations

Record count of timestamps where:

`Ticks % TimeSpan.TicksPerMinute != 0`

Record first offending index/context.

This is observational only.

Do not reject the snapshot merely because a timestamp is not minute-aligned.

## Date coverage

Record bounded raw-date counts derived from the returned DateTime values.

The date representation must be explicitly labelled:

`RAW_DATETIME_DATE_NO_TIMEZONE_INTERPRETATION`

Maximum date buckets: 32.

Fail closed if the bound is exceeded.

## Snapshot integrity

Before characterization:

- validate request identity
- validate NQ DEC26
- validate Minute/1 Last
- validate CME US Index Futures ETH
- validate Repository / DoNotMerge
- validate operator gates
- validate application timezone UTC
- reject Playback
- calculate bounded snapshot fingerprint

After characterization:

- confirm Bars.Count unchanged
- confirm snapshot fingerprint unchanged

## Evidence

Use a fresh private output directory.

Suggested files:

- `timestamp-domain-probe.jsonl`
- `timestamp-domain-probe.done.json`

Successful evidence must be sealed.

The seal must bind:

- SHA256
- byte count
- record count
- probe UUID
- request UUID
- returned rows
- BarsRequest count
- diagnostic complete
- writer closed

## Bounded evidence

Do not emit one record per bar.

Persist:

- attempt start
- request lifecycle
- snapshot verified
- characterization summary
- bounded transition records
- completion

Maximum records and bytes must be explicit.

## Fail closed

Fail closed on:

- invalid operator gates
- wrong instrument
- wrong timeframe
- wrong trading-hours template
- Playback
- wrong application timezone
- request error
- duplicate/reentrant callback
- invalid snapshot size
- snapshot mutation
- Bars.Count mutation
- GetTime exception
- transition overflow
- date-bucket overflow
- malformed evidence
- seal mismatch
- foreign files in output directory

## Interpretation boundary

A successful R5.2 run may establish the raw DateTime.Kind distribution and
transition structure of the BarsRequest snapshot.

It must not establish:

- timezone meaning of DateTimeKind.Unspecified
- conversion authority
- SessionIterator root cause
- historical bootstrap repair
- historical admission authority
- trading or execution authority

## Next gate

Only after native R5.2 evidence is reviewed may a later sprint determine
whether a timestamp interpretation experiment is justified.

No SessionIterator experiment belongs in R5.2.
