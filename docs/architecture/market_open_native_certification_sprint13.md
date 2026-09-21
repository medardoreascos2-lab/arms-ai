# Sprint 13 bounded market-open native certification

Status: **PASS_BOUNDED_MARKET_OPEN_ONLY**. This records the completed native
market-data capture, not completion of Sprint 13, session lifecycle certification,
SIM eligibility or execution readiness. Exporter, reader, freshness limits and
risk policy were unchanged. The earlier host-clock discrepancy was corrected
operationally before this fresh session; no timing tolerance was introduced.

## Provenance and duration

Baseline `092a126138829023fdb8ac7febf57fd6717ef572`; watcher
`a4802c12-a2eb-4a32-af06-9766f21f9589`; native session
`0e02836d-5355-40d2-82a6-4044b8e1db89`.
The approved test environment applied only to the isolated capture process.
All 15 preexisting evidence files were excluded at watcher startup. The new
HELLO arrived within the 180-second activation allowance.

HELLO was September 21, 2026 at 00:52:01.1832831 UTC. The first live poll was
00:52:01.213789 UTC. The 7500-second monotonic loop completed with exit code 0;
the report was written at 02:57:01.430077 UTC. Exact monotonic start/end values
were not serialized. The last admitted native event was 02:57:00.4029173 UTC,
giving a 7499.219634-second emitted-event span. That span is not substituted for
the configured capture duration or padded to 7500 seconds.

The machine-readable [certification](../../backend/tests/market_open_native_certification_sprint13.json)
binds the private report, matching connection sidecar, reviewed implementation,
and exact first 1748 market records by SHA-256. The native prefix hash is
`9776f52435b80e3e59f15e7ce5ebde0f03c8326c999e0c52e4b8c34a0a92c090`.
Every report trace entry matched its native record. Later exporter output is
outside this certificate. No prior failed session was resumed or merged.

## Observed gates

- Startup sidecar: same Provider31 source, both current statuses stably
  Connected, initial callback quarantine then aligned callback. Independent
  heartbeat validation led to HELLO under the reviewed readiness gate.
- HELLO: NQ DEC26, Minute/1, UTC, CME US Index Futures ETH, CLOSE labels,
  tick size 0.25, point value 20, read-only realtime source.
- 1499 connected heartbeats spanning 7496.344558 seconds. Consecutive gaps
  were 4.985397 to 5.060316 seconds, below the unchanged 15-second reader limit.
- 125 FORMING records and 123 CLOSED records; all 123 closes were admitted
  canonically in the live capture. Closed labels run 00:55 through 02:57 UTC,
  one per minute without gaps. The startup exclusion of partial bars explains
  the first two forming observations without corresponding admitted closes.
- Valid finite positive OHLC, high/low ordering, 0.25 tick alignment and
  nonnegative integer volume. Sequences 0 through 1747 are contiguous.
- No malformed, duplicate, regressed, stale-rejected or future-rejected frames.
  Both forming-start and closed-boundary delays were 0.002879 to 5.877944 seconds;
  none was early. Transport receipt freshness was checked by the unchanged live
  reader. Individual receive timestamps were not serialized for later replay.

## Complete higher timeframes

The live report contains seven 15m emissions and one 1h emission. Independent
membership and OHLCV reconstruction from the exact native prefix matched the
counts and the reviewed pure aggregator. This audit did not replay saved rows
into the live service or create any account.

Complete 15m buckets start at 01:00, 01:15, 01:30, 01:45, 02:00, 02:15 and
02:30 UTC. The complete hour covers 01:00 through 02:00 UTC. Initial partial
15m/hour buckets contain six minutes; trailing partial buckets contain twelve
minutes (15m) and 57 minutes (1h). None was emitted as complete. The live report
stores HTF counts, not aggregate prices; independently reconstructed OHLCV is
not presented as a separately serialized live HTF payload.

Synthetic regression reproduces this observed interval layout with explicitly
synthetic prices, checks exact completion/aggregation, and removes constituent
minutes to prove that an incomplete hour cannot become certified by padding.

## Safety and remaining scope

Broker/order calls, native account access, completed trades, completed journal
entries, account drift and execution side effects remain zero. The authorized
harness created isolated local PAPER bookkeeping with entries disabled; this
is not a claim that it avoided local bookkeeping or accessed a NinjaTrader
account. The audit did not open that database. No fabricated candles were
introduced into the native evidence. Raw individual ticks and independent
exchange clock attestation are not exported by this protocol.

Calendar hashes and the ordinary loaded-native binding passed before and after
capture. This snapshot does not establish future configuration or clock health.
Daily close/reopen, continuous weekly boundaries, holiday/early-close handling,
spring DST and provider disconnect/reconnect certification remain pending.
Holiday admission remains fail-closed. No SIM account proof has been accepted;
read-only discovery is not implemented and external SIM testing is not ready.
Thresholds remain production 90, paper 80.5 and quality 85.
This certificate does not flip runtime readiness or dashboard authority flags.
No frontend, API, native source or execution-policy change is included.

No operator action is required for this finalization. Leave the current chart
and exporter unchanged. Next is separately planned daily-boundary certification
within the reviewed dates; no new watcher was armed here. Further safe offline
work may continue, but this milestone grants no execution authority.

## Validation

The final relevant regression run passed 1013 tests with no failures or skips,
including six new certification/aggregation cases. Coverage includes Sprint
10/11T/12/13, native reader/startup/calendar/certification, current freshness,
HTF completeness, historical execution/accounting safety and MVP safety.
The machine-readable certificate lists the exact modules and command. Tests
used the existing approved test profile and private dataset mapping only in
the test process. One existing Starlette/httpx deprecation warning remains.
Frontend checks and native recompilation were not required because those
sources were unchanged. Diff, privacy and protected-evidence checks passed.
