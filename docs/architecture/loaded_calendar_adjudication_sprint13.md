# Sprint 13 loaded-calendar adjudication

Baseline `1eb1804e1a3db3cecc657025449c141821eec4e3`.
This supersedes the ordinary loaded-calendar blocker in the initial Sprint 13
report. No account access, native activation, orders or exporter edits occurred
during this adjudication. All original JSONL files stay private and unchanged.

## Evidence and identity

Exactly one artifact with schema `arms.nt.calendar-evidence.v1` was found:
`6741b746-6f31-4d26-86b2-524a901bc256.calendar.jsonl`, captured at
`2026-09-20T06:03:11.4179026Z`. It is a complete, newline-terminated single
record. Raw SHA-256:
`c7d1d601d758ee98e2aa314384ef997f388d1c3e454d205e71dbfa9795f04cf8`.

Static template SHA-256 remains
`370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620`.
The loaded template is CME US Index Futures ETH, version 5119, Central
Standard Time. Instrument NQ DEC26, Minute/1, tick .25, point value 20 and
UTC application settings match. Expiry December 1 is month metadata only.

These are **two different artifact hashes**, linked by semantic comparison;
NinjaTrader did not expose a loaded XML byte hash or platform signature.
The raw witness hash is pinned in the validator, not accepted from a user
assertion. Both evidence files are checked before capture and after it ends.
The committed adjudication contains privacy-safe native metadata and an
independently extracted static reference. No prices, account identifiers,
connection names, credentials or personal paths are included.

## Findings

| Classification | Evidence |
|---|---|
| STATIC_TEMPLATE_MATCH | Original XML hash, version and definitions unchanged |
| LOADED_NATIVE_MATCH | Five weekly sessions; 31 full-holiday dates; 112 partial-holiday dates; eleven 2026 early-close constraints; thirteen iterator probes |
| NATIVE_ONLY_INFORMATION | UTC boundary Kind with PC timezone Eastern Standard Time; exchange trading date returned for each probe |
| UNAVAILABLE_NATIVE_INFORMATION | Loaded XML byte hash, GetNextSession Boolean return, spring DST probe, continuous future configuration attestation |
| MISMATCH | None in the exposed and compared fields |

The weekly sessions start Sunday-Thursday at 17:00 Chicago and end the next
day at 16:00. The September probes map these to 22:00/21:00 UTC. After the
November DST transition, boundaries shift to 23:00/22:00 UTC. This confirms
the sampled fall transition; it is not observation of a market actually
closing or reopening, nor certification of the unqueried spring transition.

The September 21 evening session has trading date September 22. Thanksgiving
ends November 26 at 18:00 UTC, the following trading day ends November 27 at
18:15 UTC, and Christmas Eve ends December 24 at 18:15 UTC. The Christmas
query advances to December 27 at 23:00 UTC, trading date December 28.
Late-December template queries do not extend NQ DEC26 contract eligibility.

At an exact close, `includes_end=true` returns the ending session. This is
consistent with [GetNextSession's end-timestamp parameter](https://docs.ninjatrader.com/ninjascript/getnextsession).
It does not mean the forming interval after that timestamp is OPEN. The
regression verifies that September 21 at 21:00 UTC remains DAILY_MAINTENANCE
for current admission. [Template timezone metadata](https://docs.ninjatrader.com/ninjascript/timezoneinfo)
is compared independently with the UTC iterator output.

## Cleared scope and retained limits

`LOADED_NATIVE_BINDING_PENDING` is cleared **for the reviewed ordinary capture
dates only**. The specification remains September 21 00:00 UTC through
September 28 00:00 UTC, with no automatic extension or rollover. Both the
source XML and exact native witness must be present and unchanged. Invalid,
missing, unreviewed or contradictory evidence fails closed before a runtime
or state database is created. No operator Boolean bypass exists.

This is reviewed snapshot provenance, not proof that configuration can never
change later. Keep chart timezone, instrument and template unchanged during
the planned test. A template/configuration change requires a new review.
Provider31 identity remains the separate market reader/HELLO gate; the
calendar collector does not claim to identify the provider.

Holiday definitions and the sampled native projections match, but holiday
runtime admission remains blocked. The existing civil-date representation
cannot express an early close plus next-trading-day evening reopen safely
in one window. No exception dates were admitted or removed from quarantine.
The continuous weekly test still exceeds the current bounded recorder and
is design-only. SIM classification remains UNKNOWN and discovery disabled.

## Next native tests

No new calendar capture or closed-market smoke is needed. The private
resolved spec is `.arms-dev/sprint13-loaded/native_capture_spec.json`.
Codex should start the bounded harness **before** the operator removes and
re-adds the unchanged ArmsReadOnlyMarketV1. Do not reuse an existing stream.
Use NQ DEC26, Minute/1, UTC, CME US Index Futures ETH, Provider31 and the
existing private `.arms-dev/ninjatrader-current` directory inside the repo.

Market-open capture: choose an ordinary OPEN interval within the reviewed
dates with at least 125 minutes before scheduled close. Use purpose
`market_open`, duration 7500 seconds, fresh isolated state and output paths.
The first allowed start is September 21 00:00 UTC. No strategy signal or
profitability requirement applies; closed 1m and complete 15m/1h evidence do.

Daily-boundary capture: a covered Monday-Thursday, begin at 20:45 UTC
(15:45 Chicago), purpose `daily_boundary`, duration 8700 seconds. Observe
OPEN -> DAILY_MAINTENANCE -> REOPENING -> OPEN, continuous heartbeat evidence,
fresh post-reopen closes and current-session HTF bars. Do not fabricate bars
or relabel a delayed pre-close candle fresh. A stale candle emitted on reopen
must fail certification and be reviewed; this remains a pending native test.

Typical agent-side command, with fresh filenames selected per capture:

```powershell
py -m backend.market_data.native_certification_v1 --spec .arms-dev/sprint13-loaded/native_capture_spec.json --directory .arms-dev/ninjatrader-current --state .arms-dev/sprint13-loaded/NEW_CAPTURE.sqlite --output .arms-dev/sprint13-loaded/NEW_CAPTURE.json --purpose market_open --seconds 7500
```

The configured risk settings must be present; no default risk values or account
configuration are introduced. Do not start this command during this audit.
Market-open, daily/weekly/holiday lifecycle, disconnect/reconnect and external
SIM work are not certified by a metadata match. Orders remain disabled.
