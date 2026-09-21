# Sprint 15X: operation-specific time authority

Baseline: `b25c6ce7020dcfdc08f42d8524673ebeb20a7100` on
`refactor/backend-architecture`. No native activation or commit is authorized by
this implementation. Canonical schema, exporter, timestamp tolerances, existing
current-market admission and execution gates remain unchanged.

## Result and proof boundary

Source-relative descriptive analysis is possible without knowing true current
UTC. Fresh certified **absolute-current-market analysis is not yet proven**.
The profile never promotes one into the other. The existing Sprint 15W native
certificate establishes exact canonical/production-sidecar correspondence for
its recorded stream (`PASS_STREAM_ONLY`). It does not attest the current source
time, absolute reference error, QPC drift, current calendar binding or a future
reader's same-host epoch. Hashes establish correspondence, not authenticity.

The new object is an isolated, explicit in-process consumer. It does not open
files, start a watcher, connect to NinjaTrader, instantiate an account or attach
to the existing PAPER runtime. Its injected delivery/clock boundary is suitable
for offline fault tests; native attachment needs the reviewed adapter described
below. A caller-supplied epoch or exporter hash is a prerequisite assertion, not
proof that native attachment has happened.

The previous `NinjaTraderMarketReaderV1` feeds `CurrentPaperServiceV1`, whose
first admitted close can instantiate PAPER accounting even with entries
disabled. Using that path would violate this sprint's zero-account-access
requirement. Neither that reader nor its stronger admission checks are changed.

## Minimum authority partition

Abbreviations: S = SOURCE_TIME, C = CANONICAL_SEQUENCE, Q = MONOTONIC_QPC,
H = HOST_UTC, A = QUALIFIED_ABSOLUTE_TIME. Identity, exact row pairing, trusted
delivery and required domain policies are additional prerequisites, not clocks.
H is diagnostic observation, never an independent accuracy certificate.

| Operation | Minimum authority | Scope and unavailable dependent property |
|---|---|---|
| Record ordering | C + session identity | Consecutive sequence from fresh HELLO; Q checks emission order independently. H not required. |
| Duplicate detection | C + session identity | Repeated sequence or pair rejected; S additionally identifies repeated bars. |
| FORMING/CLOSED identity | S + C | Bar index, bars-ago and same callback pairing; Q proves callback/emission chronology. |
| Canonical 1m continuity | S + C | Exact adjacent minute labels and bar indices; not proof of current market recency. |
| 15m aggregation | S + C | All 15 completed contiguous constituent minutes; no filling, clock-triggered closure or session inference. |
| 1h aggregation | S + C | All 60 constituents; same restrictions as 15m. |
| Heartbeat liveness | Q + C | Local receipt activity only. Unpaired heartbeats cannot prove exporter emission age. |
| Local processing age | Q | Same-host/epoch emission-to-now and receipt-to-now deltas; nominal QPC seconds only without drift bounds. |
| Transport freshness | Q + C + exact pairing | Local exporter-to-reader observation age. Exchange-to-exporter latency and absolute market recency remain UNKNOWN. |
| Source-time recency | S + A | Compare certified source semantics with a qualified current-time interval; relative progression alone is insufficient. |
| Session/calendar admission | S + reviewed current calendar binding for label membership; A for “current session” | Old snapshot and template name do not prove this stream's loaded contents. SESSION_STATUS=UNKNOWN. |
| Daily/weekly boundaries | S + calendar for source-relative grouping; A for current boundary decisions | Numeric minute buckets do not grant daily/weekly session, reset or risk authority. |
| News blackout | A + authoritative news schedule | NEWS_UNCERTIFIED blocks news-dependent decisions and entries. |
| Risk timing | Q for local durations; A + session policy for wall/calendar deadlines | No risk deadline, daily reset or eligibility is supplied by this profile. |
| Journal chronology | C + Q for local order; A for qualified cross-system chronology | H can be retained as unqualified metadata. No journal writes here. |
| PAPER entry | S + C + Q + A as required by full market/news/session/risk policies | This profile supplies no entry token; DISABLED even when descriptive observations exist. |
| SIM execution | Same operation requirements plus explicit SIM identity and authorization | DISABLED. No account discovery, binding or order preparation. |
| LIVE execution | Same operation requirements plus independent LIVE authorization and safeguards | NO. Analysis readiness grants no execution authority. |

Qualified absolute time must carry error/drift bounds adequate for each operation
window. The unchanged Sprint 15T interval model remains authoritative for that
question. No new tolerance, NTP assumption or guessed bound closes it.

## Profile and fault handling

`MarketAnalysisTimeProfileV1` requires a new session UUID, explicit QPC epoch and
frequency, a reader-start QPC before the first native callback, a clock function,
explicit local observation budgets and the reviewed exporter source fingerprint.
There are no production budget defaults. The synthetic tests use 15 nominal
seconds between receipts and 90 nominal seconds since emission to exercise
minute boundaries; these are test inputs, not a new certified timestamp policy.

Canonical rows must retain the exact `arms.nt.market.v1` schema. Each FORMING or
CLOSED row requires the existing `arms.nt.production-timing.v1` sidecar with
exact raw-row SHA256, contiguous canonical/pair sequences, fixed Provider31 /
NQ DEC26 / Minute 1 / UTC / CME US Index Futures ETH identity and realtime
callback metadata. UTC text/ticks are checked for internal consistency only.
Changing the host clock cannot grant absolute authority. QPC ordering and age
are independently checked. Previously captured callbacks before reader start
are rejected.

The first realtime forming bar is excluded from completed analysis. A CLOSED
record remains pending until its adjacent FORMING record proves the same
callback. Only then is a detached completed candle released to the pure engines.
No partial HTF bucket is projected. Bounded history is 120 one-minute candles
and 50 aggregates per timeframe; there is no retained raw stream or account state.

Sequence gaps, duplicates, out-of-order data, mismatched hashes/pairs/identity,
source-label gaps, loss of receipt activity, expired paired emissions, QPC loss,
regression, epoch change, terminal records and explicit restart/reconnect
revocation latch failure. All component values then disappear. A later heartbeat
or bar cannot reset that latch. Recovery requires a new object and independently
re-established fresh attachment; no persisted recovery or automatic promotion.

Freshness is exposed separately:

* TRANSPORT_LIVENESS: observed local receipts, not qualified upstream freshness.
* PROCESSING_AGE: nominal QPC delta since exact exporter emission, not a
  drift-qualified upper bound in SI seconds.
* CANONICAL_CONTINUITY: contiguous observed prefix, not universal history.
* SOURCE_TIME_STATUS: labels and relative progress only.
* SOURCE_TIME_RECENCY and ABSOLUTE_MARKET_RECENCY: UNKNOWN.
* DATA_FRESHNESS: NOT_ASSERTED; never whole-feed FRESH.

## Session and component review

The exact previously reviewed native calendar bytes can be compared against the
reviewed template representation. Invalid evidence is rejected. Valid evidence
is `REVIEWED_SNAPSHOT_ONLY`: the production sidecar contains the template name,
not a continuously checked calendar digest or iterator identity. Consequently
neither valid old evidence nor a host timestamp establishes current session
admission. Session-dependent analysis remains unavailable, including daily/
weekly liquidity/session ranges and maintenance/holiday eligibility.

| Component | Reused implementation / evidence | Exposed result |
|---|---|---|
| 1m | Complete matching CLOSED/FORMING boundary | Last completed close and source-open label; source-relative only. |
| 15m / 1h | `ClosedBarAggregatorV1`, complete Chicago-aligned buckets | Last fully completed aggregate close/source-open; no current session assertion. |
| Trend | `TrendEngineV2`, default 10/50 EMA and 5-bar slope | Direction, EMA and slope after 50 complete bars. Engine confidence excluded. |
| Structure | `MarketStructureEngine`, at least 3 bars | Pure price-pattern classification; no session or entry claim. |
| Liquidity | `LiquidityEngine`, at least 4 bars | Equal-level/sweep pattern using existing default tolerance; no daily/session liquidity claim. |
| FVG | `SmartMoneyEngineV2.detect_fvg`, last 3 completed bars | Price-gap observation; no tradability claim. |
| Regime | `MarketRegimeEngine` requires independently wired/calibrated metrics and thresholds | NOT_PROJECTED; missing reviewed input policy, not intrinsically a wall-clock dependency. |
| Confluence | `ConfluenceEngineV2` consumes broader component/risk/sizing/tradability context | NOT_PROJECTED; no invented approvals or incomplete score. |
| Confidence | Probability/confidence engines require full reviewed evidence/policy | NOT_PROJECTED; no fabricated confidence or strength-as-probability. |
| Decision | Existing `LiveMarketAnalysisService` has account/order-preparation dependencies | NOT_PROJECTED; never invoked by this isolated profile. |

These descriptions qualify numeric observations, not a certified trading signal.
Engine outputs cannot be consumed by PAPER here: there is no runtime handle,
order constructor, account adapter, journal or mutation route in the app.

## Dashboard/API contract

The explicit `create_market_analysis_time_app_v1(profile=...)` factory exposes
only GET `/api/v2/market-analysis/time-profile` plus FastAPI's schema route.
It does not start a service or register with the existing account-backed app.
The separate `/market-analysis` page polls this endpoint using existing transport
configuration, without credentials or execution controls. No existing dashboard
account subscription is reused. No configuration is changed by this sprint.

`MARKET_STREAM=LIVE` has the explicit meaning **local exporter observations**,
not fresh exchange data. UI displays processing, continuity, source-time,
absolute-time, session and news authorities separately. It rejects contradictory
authority claims, allowlists component fields, drops unknown/private strings,
clears responses on failures/visibility changes and expires them locally after
two seconds. Browser polling is a sampled observation, not an atomic live-market
guarantee. Missing service displays BLOCKED, not fallback/demo data.

EXECUTION_MODE=LOCAL_PAPER is only a mode label. PAPER_ENTRY_AUTHORITY=DISABLED,
SIM_EXECUTION_AUTHORITY=DISABLED, LIVE_AUTHORITY=NO. There is no PAPER account
initialization, NinjaTrader account access or broker request.

## Offline validation and preservation

`test_analysis_time_sprint15x.py` exercises healthy completed data, full/incomplete
HTF, uncertain host UTC, unknown absolute/session/news authority, calendar
acceptance/rejection, heartbeat/processing expiration, sequence/pair faults,
restart/reconnect, epoch failures, GET-only API and zero account/runtime/order
construction. Synthetic tests are not labeled native evidence. Frontend tests
verify projection authority separation and no stale/unsafe component values.

Sprint 15T's exhaustive clock inventory gains one explicit dependency entry
marked as introduced by Sprint 15X. All prior inventory entries, clock assessment,
bounds and readiness fields remain unchanged. Its test stays byte-for-byte
unchanged because Sprint 15W fingerprints it. Existing Sprint 15U/V/W/R1 evidence
and native source fingerprints remain frozen. Regression
commands/results and byte-preservation checks are recorded in the local
`.arms-dev/sprint15x` validation artifacts; the review JSON is not a new native
capture certificate.

## Shortest native activation path — not armed

1. Review and offline-test a dedicated read-only file adapter for this profile:
   new empty isolated directory, fresh exporter lifecycle and UUID, same Windows
   QPC epoch/frequency and reader-start proof, current installed exporter identity,
   bounded incremental reads, atomic row/sidecar delivery, receipt timestamps,
   missing/late sidecars, file replacement/truncation and connection/terminal
   revocation. A sidecar seal is terminal archival evidence, not something to
   fabricate while the exporter is running. Trust cannot be established by
   copying a filename, old rows or merely supplying a constructor hash.
2. Review explicit local liveness/processing observation budgets without changing
   the existing certified absolute-time tolerances. Do not describe nominal QPC
   age as a drift-qualified elapsed bound. Current-session and upstream freshness
   remain unavailable unless separately proven.
3. Instantiate only the isolated profile/API with that adapter, before operator
   activation. Verify empty inbox, live process/advancing heartbeat and dashboard
   unavailable state. Do not instantiate `CurrentPaperServiceV1`.
4. Obtain explicit authorization for continuous read-only native activation, then
   let the operator activate the existing compiled exporter. Warm up using only
   fresh completed bars (at least a complete aligned hour for 1h). No old evidence
   reuse, PAPER entries, account access or execution.

Another bounded capture solely to re-prove unchanged emission pairing is **not
required**. Simply activating the exporter today is **not sufficient**: the fresh
attachment/epoch adapter is not implemented in this sprint, and absolute recency
and current-session authority remain unproven. The implemented offline profile
can expose only the justified source-relative properties. Full LIVE MARKET
ANALYSIS and LIVE MARKET PAPER SOAK remain NOT_READY. No human native action is
requested now. The next step is the adapter review/integration above, not another
timing-pairing capture or a relaxation of absolute-time gates.

Exact proposed commit scope is in
`backend/tests/market_analysis_time_sprint15x.json`. No commit or push performed.

## Validation result

* Backend: 1,555 passed across the 42 modules listed in the review JSON, including
  31 Sprint 15X tests. `python -B -m pytest` with `-q -x --tb=short`, disabled pytest
  cache, a fresh workspace basetemp and JUnit output. Existing Starlette/httpx
  deprecation warning only; no failures or skips.
* Frontend: `node --test src/lib/*.test.mjs` — 37 passed;
  `npm.cmd run lint` — PASS; `npm.cmd run build` — PASS. The build used the existing
  Google Fonts download; no dependency or Windows configuration was changed.
* `git diff --check` and whitespace checks of all new scope files — PASS.
* Byte preservation: all 971 files in the prior preservation manifest unchanged,
  all 16 previous combined-sprint source fingerprints unchanged, 109 unrelated
  files, 16 datasets, 18 native evidence entries and 11 R4 evidence files preserved.
* These are offline validation results, not proof of a currently attached native
  stream, current session or accurate absolute time.
