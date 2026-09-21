# Sprint 15Z: certified historical warm-up (offline implementation)

Baseline: `f17638e44d2bdecedc799873301536ee51bbe626`, branch
`refactor/backend-architecture`. No deployment, commit, push, native activation,
exporter edit, Windows change, or timing-budget change is part of this phase.

## Problem and resulting behavior

15Y deliberately discards the startup prefix and initializes analysis only from
fully observed fresh minutes. It therefore cannot recover historical indicator
state on restart. It projects Trend only at 1m. 15Z adds an optional, explicitly
reviewed history input, independent of the native live inbox, and Trend at all
three timeframes. The default without history remains the existing cold start.

Historical analysis can be visible while transport is NOT_LIVE. The displayed
status is **CERTIFIED_BOOTSTRAP_ONLY**, never SOURCE_RELATIVE_ONLY or a fresh
receipt. No historical bar enters `live_delivered_records`, live canonical
sequence, emission age, receipt age, background heartbeat, or startup cursor.

## Data classes and trust boundary

* `CERTIFIED_BOOTSTRAP`: validated historical completed bars, immutable in memory.
* `LIVE_TAIL`: newly admitted records after the independent 15Y cursor/QPC fence.
* `UNTRUSTED_HISTORY`: absent proof or invalid history, never admitted to analysis.
* `REVOKED`: a failed live/handoff proof suppresses all analytical values, including
  historical values. There is no automatic restoration or downgrade-to-trusted.

The bundle schema is `arms.certified-bootstrap.v1`: exactly `schema`,
`authored_sha256`, and an ordered list of `segments`. Each segment contains the
unaltered UTF-8 canonical stream, production timing sidecar and final native seal
as `canonical_utf8`, `timing_utf8`, `seal_utf8`. The caller supplies an independent
reviewed SHA256 of the **whole bundle**. A hash found inside a file is insufficient.
Every restart reloads bounded bytes and repeats validation against that pin.

Certification means structural, source-relative provenance within the reviewed
operator-controlled native acquisition boundary. Hashes do not authenticate a
writer. The authored-source hash is the existing R1 compatibility identity;
neither a source hash nor a seal attests a compiled assembly, UTC accuracy,
current market recency, loaded calendar contents, or broker entitlement. An
arbitrary JSON file with fabricated matching hashes is not an authorized source.
Do not treat the synthetic test generator as a historical data provider.

Required proof includes:

* Exact Provider31, NQ DEC26, expiry 2026-12-01, NQ 1m, UTC CLOSE labels,
  CME US Index Futures ETH, tick .25, point value 20, read-only realtime metadata.
* Exactly one HELLO and final DISCONNECTED per segment; complete native seal,
  matching byte/record counts and sidecar hash; all canonical sequences starting
  at zero and contiguous; no extra, missing or ambiguous JSON fields/keys.
* A bijection between canonical bar rows and hash-bound timing pairs, stable
  source identity/frequency, valid UTC/QPC pair geometry and ordered callbacks.
  These archived clocks are checked for internal consistency only, never reused
  as the new runtime clock or receipt observations.
* Valid positive tick-aligned OHLC, finite values, integer nonnegative Int64
  volume, exact minute labels, observed forming-to-closed correspondence and
  same-callback CLOSED/FORMING pairing. The initial partial bar is excluded.
* Strict minute order within a segment; no duplicate or missing minute is
  accepted within it. Separate sealed segments must have distinct session IDs,
  ascending nonoverlapping labels, and the same contract. Inter-segment gaps
  remain explicit as `bootstrap_gap_count`; they are never filled.

Bounds: 64 MiB bundle/read limit, 128 segments, 200,000 rows per segment,
16 KiB per row and 10,000 completed bars. Oversize, unsealed, missing, invalid or
pin-mismatched explicitly requested evidence fails startup; it cannot silently
fall back to cold history. Source files are never modified by the loader.

## Rollover policy

Only the exact current reviewed contract **NQ DEC26** is accepted. Prior contract,
rollover boundary, mixed contracts, back-adjusted/continuous futures and arbitrary
CSV are rejected. Prior-contract history is **not** used even for indicator-only
initialization in this version. Supporting a later contract requires a separate
identity/rollover review; no implicit mapping by instrument name is permitted.

## Aggregation and production Trend

Use the existing `ClosedBarAggregatorV1` unchanged: UTC canonical CLOSE labels
become aware OPEN labels by subtracting one minute. The existing Chicago-aligned
buckets require every constituent minute, exactly once: 15 for 15m and 60 for
1h. Partial leading/trailing buckets and buckets spanning any missing minute
are not emitted. No session calendar, holiday, pause or missing minute is
inferred from the template name. A complete bucket proves constituents only.

The existing `TrendEngineV2` defaults remain EMA10, EMA50, slope lookback 5,
sideways threshold .0005. Exactly 50 completed bars are required independently
at each timeframe: 50 minutes, 750 minutes forming 50 complete quarter-hours,
and 3,000 minutes forming 50 complete hours. Acquisition needs additional
padding for discarded initial bars, partial buckets and session gaps. The
engine uses the latest 50 completed bars; no period or threshold is reduced.
Across explicitly disclosed historical segment gaps these are historical
indicator samples, not proof of uninterrupted current-price continuity.

Trend direction, EMA values and slope are projected. The engine's internal
confidence score is deliberately omitted. Regime, Confluence, Confidence and
Decision stay NOT_PROJECTED. Structure, Liquidity and FVG use the unchanged
engines with seeded history, then recompute only on admitted completed live bars.

## Deterministic handoff and restart limitations

History is validated and initialized before a live adapter is prepared. It is
not written into the inbox. The health-first order and exclusive fresh inbox
remain unchanged. The adapter establishes its own byte cursor and fresh QPC
epoch, discards its ordinary untrusted prefix, and records the first admitted
live FORMING sequence/label independently of the fixed bootstrap cutoff. The
first eligible completed live bar is also recorded. First partial bars remain
excluded exactly as in 15Y.

At each completed live bar:

1. A label at/before the cutoff must exist in the certified data and have identical
   OHLCV. A matching overlap increments only `overlap_minutes_skipped`; no candle,
   bucket or indicator is added/recomputed. State remains VERIFYING_OVERLAP.
2. The first new label must immediately follow the certified cutoff; subsequent
   labels must immediately follow the latest admitted minute. Gaps, missing
   overlap labels or conflicting OHLCV revoke the profile and adapter.
3. Handoff becomes COMPLETE only on the first new completed live minute. All
   subsequent analytical updates come from admitted live completed bars.

Fresh transport does not relabel old hourly/quarter-hour values: those remain
CERTIFIED_BOOTSTRAP_ONLY until a new complete live bucket is emitted. 1m and the
last-minute derived components then become SOURCE_RELATIVE_ONLY, with bootstrap
context explicitly retained in the API. `trend` remains a compatibility alias
for `trend_1m`. Counts and latest complete OPEN labels are independent per HTF.

Clean/adapter/backend restarts and new exporter sessions can restore certified
analytical history but **cannot restore live authority, receipt clocks, sequence,
cursor or liveness**. Each new object needs a new admission proof. A restart
avoids re-collecting an hour only when the available history and observed tail
actually prove the handoff. A normal stop/start can leave excluded startup
minutes or a real observation gap: **this version rejects that handoff**. It
does not promise seamless recovery through arbitrary downtime or stitch a gap
using an uncertified startup prefix. A contiguous bridge must first be acquired
and certified, or a separately authorized cold start must be used. This is an
explicit transition blocker, not a reason to weaken the checks.

## API, dashboard and offline tooling

The existing GET endpoint carries bootstrap status/source/hash/bar count/cutoff,
gap count, handoff state, first live/first completed live identities, overlap
count, `complete_buckets`, and per-timeframe Trend. No new HTTP write route exists.
The dashboard validates historical class and proof metadata before showing
initialized values. It retains ANALYSIS ONLY, absolute recency UNKNOWN, session
authority UNKNOWN, news UNCERTIFIED, and disabled execution disclosures. An
unavailable response still clears locally and expires after two seconds.

`python -B -m tools.certify_analysis_bootstrap_v1 --help` describes explicit
offline creation from one or more ordered `--segment CANONICAL TIMING SEAL`
triples, `--exporter-source`, and a new `--output` file. It validates before
creating output exclusively, prints a candidate pin, and never starts a runtime.
Review acquisition provenance and that pin independently before use.

The existing health-first launcher accepts paired optional
`--bootstrap-evidence ABSOLUTE_BUNDLE_PATH --bootstrap-sha256 REVIEWED_PIN`.
It validates before starting services. Do not point it at a live inbox or
substitute test evidence. No changes were made to the exporter or its properties;
NinjaTrader recompilation is not required.

## Available native evidence and transition gate

The committed Sprint 15W capture (also adjudicated by 15W-R1) is the safest
available immutable native source reviewed here: session
`f36aeebc-0ca7-4079-a318-55cce9d38602`, eight completed minutes, CLOSE labels
15:09 through 15:16 UTC on 2026-09-21. It passes the historical contract but
produces **zero complete 15m and zero complete 1h buckets**, and no Trend.
It cannot bridge to the current tail. Its template identity proves no additional
calendar authority. The active 15Y run was inspected only as operational evidence;
its mutable files were not repurposed as the offline bootstrap dataset.

The 3,000-minute/50-hour results are **synthetic regression evidence only**.
No sufficient native bootstrap has been acquired or deployed in this phase.
Current runtime UUID `8260a1d7-d6aa-4b53-a78a-f525bdbc0fa3` remains on 15Y-R1.
No process restart, activation allowance, cursor/session mutation or native UI
operation was performed.

Controlled transition is blocked pending sufficient same-contract native history
and a proven handoff. The safe order is: review the offline change and exact
commit scope; obtain explicit commit authorization; acquire/review adequate sealed
history and a contiguous handoff plan; preserve current runtime evidence and
manifests; obtain operator readiness and transition authorization; then use a
fresh UUID/inbox and the existing health-first startup contract. The operator
alone configures/activates the native exporter. If a gap cannot be proven away,
stop the transition review rather than treating old history as live or weakening
the handoff. Do not stop the current working runtime just to attempt this plan.

## Validation and safety

The machine-readable review is `backend/tests/certified_bootstrap_sprint15z.json`.
It separates acquired native history from synthetic tests, lists exact source
hashes and validation results, and records proposed scope. The private test,
build and preservation reports are isolated under `.arms-dev/sprint15z`.

PAPER entry and SIM execution remain DISABLED; LIVE authority NO; broker order
calls and PAPER trades zero; NinjaTrader account access and order-submit reachability
false. Backend tests instrument forbidden account/execution constructors and check
read-only API behavior. No timing tolerances or prior clock authority assessments
changed; only three clock-inventory source line numbers moved.
