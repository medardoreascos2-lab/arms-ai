# Sprint 15T: formal clock preflight (offline only)

Baseline: `905db9ea4a5efbf61e990c60c737fec1d82cdd88`.

The existing runtime is unchanged. `tools/clock_preflight_v1.py` is a pure,
offline executable specification. It reads no clocks, calls no network, imports
no execution/runtime coordinator, and cannot arm ingestion. Its input values
are explicit assumptions/evidence, not credentials or native account metadata.
The machine contract and dependency inventory are in
`backend/tests/clock_preflight_sprint15t.json`; regression cases are in
`backend/tests/test_clock_preflight_sprint15t.py`.

## Finding and scope

The Sprint 13 native certificate proves a bounded ordinary-open capture, not
a universal NTP-offset threshold. The minimum recorded boundary headroom of
2,879 microseconds is not a clock-error allowance. It includes unknown callback
delay and the then-current host error. Original exchange-authenticated time and
per-record receipt times were not exported. Daily/weekly/holiday boundary
certifications remain separate. No threshold can be reverse-engineered from a
successful capture to authorize the currently measured 137-139 ms lag.

The prior informal clock PASS/FAIL reports are superseded for readiness purposes
by explicit UNKNOWN when error/drift bounds or operation windows are missing.
This does not retroactively invalidate the bounded native observation or claim
that the Windows clock has no measurable improvement.

## Wall-clock dependency inventory

The JSON inventory records direct call sites (module, line, expression,
consequence) throughout backend Python excluding tests and NinjaTrader sources.
It also records indirect timestamp consumers and frontend timing dependencies.
Line numbers refer to this baseline; these are not a claim that all alternate
execution modules are reachable from the isolated Sprint 15 dashboard host.

| Dependency/path | Time authority and consequence |
| --- | --- |
| `ArmsReadOnlyMarketV1.cs` | `DateTime.UtcNow` envelopes and connection observations; native `Time[ago]` CLOSE labels, under checked application UTC, define bar identity. Host emission is not authenticated exchange event time. Startup uses Stopwatch and bounded timer; polling samples cannot manufacture bars. |
| `ArmsCalendarEvidenceV1.cs`, connection observer, SIM witness | Host capture timestamps plus native session labels / monotonic observation duration. Evidence freshness/provenance only. SIM witness is inventoried, never executed by this sprint. |
| `ninjatrader_market_reader_v1.py` | Injected host receipt time, HELLO identity/freshness, stream ordering, heartbeat age and timeout; failures latch transport recovery. Common host offset can cancel between emission/receipt without validating absolute UTC. |
| `current_candle_authority_v1.py` | Host now/receipt/emission versus source-defined start/close; future/stale rejection; last-close freshness; calendar extent and sequence continuity. Wrong UTC can cause false rejection or optimistic age at a limit. |
| `native_certification_v1.py`, `operational_paper_soak_v1.py` | Wall UTC for calendar/runway, fresh session matching and report timestamps. Existing activation/capture budgets already use monotonic deadlines. Never replace those with wall sleeps. |
| `session_state_v1.py`, `market_hours_service_v2.py`, special-hours/calendar snapshots | Caller UTC -> exchange zone, trading date, daily maintenance, weekly close/reopen, holiday/early-close coverage. Unknown coverage fails closed. Calendar and connectivity are independent. |
| `closed_bar_aggregator_v1.py` | No host clock. Ordered canonical source labels and all 15/60 constituent minutes determine complete buckets. Missing intervals never filled. Clock error affects upstream eligibility, not bucket arithmetic. |
| `current_paper_runtime_v1.py`, `paper_runtime_v1.py` | Admitted close drives delivery/replay clock and local account trading date; current readiness projection also uses host now. Historical replay time is not current UTC authority. |
| `operational_paper_v1.py` | Host calendar/news/recovery checks and displayed duration; entries explicitly disabled in analysis host. Display duration currently subtracts wall times and can jump; monotonic duration is a future metadata-only improvement, not required for this offline sprint. |
| `runtime_admission_v2.py`, quote/spread authorities, live analysis/candle store, price feed, market hub | Host/caller now, quote age, future checks and coverage feeding alternate runtime admission. Provider timestamps must not be silently replaced with host time. |
| economic-news authority/provider/snapshot/lifecycle + refresh API | Caller evaluation UTC and host refresh timestamps versus certified coverage/event times. Existing authority matches exact events; certified pre/post blackout policy is absent. Clock certainty cannot invent blackout coverage or news clearance. |
| account state manager, risk engine, order validation, execution engine, lifecycle, local paper connector, OCO/protection registry | Injected/wall timestamps, current quote/risk state, trading-day resets, local position events and protections. Clock readiness does not authorize any execution. These alternate components require independent call-path review before attachment. |
| journal/loggers, execution state stores, durable state, startup/recovery/shutdown coordinators | Audit timestamps, checkpoint recency and recovery ordering. Wall timestamps are not sufficient ordering/duration evidence across steps or restarts. Sequence and persisted identities remain mandatory. |
| dashboard services/APIs/websockets and frontend pages | Server freshness/session/readiness projections; wall display timestamps. Browser relative timers perform polling/reconnect/abort only; browser date is never admission authority. GET remains read-only. |
| research jobs/pipelines, legacy collector/simulator | Host metadata or legacy naive wall timestamps, inventoried but not current-feed timing authority; no use as a substitute for a certified source. |
| future SIM/LIVE | No certified external execution timing contract or enabled authority. Neither account names, provider enum, clock proof nor dashboard readiness establishes it. |

## Formal time model

All model timestamps use integer microseconds; rate bounds use integer ppb.
Rounding is outward. Production/native 100 ns strings are not rewritten.

| Symbol | Meaning / permitted decisions |
| --- | --- |
| H = HOST_TIME | Local UTC estimate, not ground truth; absolute decisions require independently justified enclosure. |
| E = SOURCE_EVENT_TIME | In current JSONL this is actually exporter host emission UTC. It must not be relabeled authenticated provider tick time. Requires its own uncertainty at emission. |
| C = BAR_CLOSE_LABEL | Source-defined UTC close boundary under reviewed Minute/1 semantics. Never recompute from local arrival or shift by estimated offset. |
| S = IMPLIED_BAR_START | C minus exactly 60 seconds for the reviewed ordinary full minute; session-clipped/unreviewed bars need separate proof, not this formula by assumption. |
| R = RECEIPT_TIME | Host UTC recorded at ingestion; pair with monotonic instant/epoch in any future proof-producing observer. Existing raw evidence does not contain that pair. |
| M = MONOTONIC_ELAPSED_TIME | Relative elapsed time within one boot/clock epoch. Suitable for timeout, capture duration, retention age; never directly a trading date. Suspension/steps must invalidate unproved rate/epoch assumptions. |
| T = TRADING_SESSION_TIME | UTC mapped through reviewed calendar/timezone/trading-date rules. Source-label membership differs from current host-based OPEN state. |
| N = NEWS_EVENT_TIME | Certified scheduled event UTC and explicit coverage/blackout endpoints. It is not event retrieval time or a fabricated empty calendar. |

Clock intervals for E, R and H cannot be obtained simply by applying today's
offset to old records. Each needs valid evidence at its own paired monotonic
instant. If source times become authenticated in future, they still need a
declared error bound and audited mapping to bar semantics.

## Machine preflight contract

`assess` consumes Sample[], ReviewedBounds, WindowsState, explicit operation
windows, current H/M/epoch and horizon. `ReviewedBounds` is a separate reviewer
input, never inferred from offset measurements or a provider's claimed quality.
Its provenance string is an audit identifier, NOT an implemented signature
verifier. This sprint supplies only synthetic reviewed bounds in tests. There
is no production trust issuer, automatic attestation or runtime integration.

Required assumptions:

1. At least two reviewed independent reference groups; at least two distinct
   receipt instants per reviewed reference. These are minimum identifiability
   requirements for cross-reference and temporal comparison, not a confidence
   level or proof of a future drift bound. All configured references participate.
2. Reference absolute error, independence and provenance are separately reviewed.
   Unauthenticated stripchart offsets/RTTs alone do not establish these bounds.
3. A reviewed upper rate-error bound covers monotonic versus UTC and host versus
   monotonic drift across the full validity interval. An observed +44.8 ppm
   adjustment is not such an upper bound. Captured-pair/quantization error is
   bounded separately. All bounds are explicit, finite nonnegative integers.
4. Monotonic epoch is pinned. Samples must lie inside the reviewed validity
   interval and cannot be from the future, another boot, or repeated as fresh
   samples. Wall/monotonic inconsistency beyond the supplied error bound rejects
   the evidence. A backward step or forward step never silently refreshes it.
5. W32Time running/automatic, reviewed source, HOLD or SYNC, last error zero,
   observed state and last sync mapped into the same monotonic epoch and validity
   interval. HOLD is neither unconditional failure nor proof of accuracy. A
   stale-sync error is UNKNOWN. Operator wall timestamps alone do not provide
   a trustworthy monotonic last-sync mapping.

For a sample with reference receive/send R2/R3, monotonic round trip d and
reference error e, the true UTC at host receipt is enclosed by:

    [R3 - e - capture_error,
     R2 + d + drift(d) + e + capture_error]

This permits all network delay on either path. It does not assume RTT/2 is an
error-free offset correction. Propagate to current M by elapsed monotonic age
plus/minus outward-rounded drift and paired-capture error. Consistency requires
the propagated enclosures to overlap; disagreement is UNKNOWN, not majority
vote. The output is the HULL of retained enclosures, not their narrowest
intersection or the lowest-RTT sample alone. Outliers cannot improve readiness.
This is deliberately conservative and may deny availability under asymmetric
delays. Consistency is not proof against common-mode reference bias.

No fixed 10/50/150 ms offset cutoff or universal sample TTL exists. Sample age
increases the envelope; a reviewed validity expiry or an envelope exceeding an
operation's margins denies readiness. For a future horizon, propagate to its
end and require the whole interval to fit a single reviewed valid operation
window. Crossing a calendar/news/expiry boundary needs a new proof; a one-time
preflight is not a lease across all future minute boundaries.

`clock_ready[MARKET_ANALYSIS|PAPER|NEWS|SIM|LIVE]` means only temporal containment
within that named, explicitly reviewed window. Missing windows remain false.
`runtime_readiness_granted` and execution authority ALWAYS remain false here.
No uncertainty is represented as zero by default; malformed/unknown input
returns UNKNOWN (typed low-level invalid interval constructors raise instead
of producing any permissive result).

## Deriving operation-specific bounds

Let true UTC at an evaluation be in [L,U], the canonical close be C, and the
existing freshness cap be A=30 seconds in the authorized profile. Sufficient
absolute conditions for a closed observation are:

    L >= C                 (definitely not future)
    U <= C + A             (definitely not stale)

For a symmetric error bound b about host H this implies:

    b <= min(H-C, C+A-H)

Intersect this with certified session/contract/coverage windows and news-clear
intervals, respecting their actual inclusive/exclusive endpoints. The margin
can be zero at a boundary; no positive universal b follows. Arbitrary fixed
latency compensation, timestamp shifting or grace periods do not prove this.

FORMING uses S and its existing 60+A age extent, not C as a current boundary.
Source close C can legitimately be in the future while S is not. E itself must
be certainly at/after S (FORMING) or C (CLOSED). Receipt and evaluation intervals
must prove ordering and maximum age too. `boundary_proof` models conservative
sufficient conditions for these inequalities; it never admits a candle.

For current-state session/news decisions, the entire true-time interval must
lie in one certified state/clear region. A fresh calendar or news snapshot is
necessary independently. Current source-label HTF membership depends on labels
and all constituent closes, not host clock rounding. PAPER requires the same
data proof plus news/risk/entry authority; no separate guessed precision number.
SIM/LIVE need future independently reviewed execution/venue contracts. Their
requirements cannot be certified from local paper observations.

## Boundary architecture investigation (not implemented)

A future observer could retain original source labels, immutable raw identity,
paired monotonic receipt and reference-bounded emission/receipt intervals. It
could quarantine an uncertain boundary observation and re-evaluate certainty
as time progresses. This is not a fixed wait/grace period. A CLOSED observation
whose emission was not proved post-close cannot become valid merely by waiting.
Unknown source semantics, bad OHLCV, duplicate conflict, reconnect or calendar
coverage still reject. No account/runtime initialization occurs in quarantine.

Required release proof obligations:

| Invariant | Necessary release condition |
| --- | --- |
| NO_FUTURE_CANDLE_ADMISSION | Source closure and emission/receipt/now lower UTC bounds are at/after the reviewed close. |
| NO_STALE_CANDLE_ADMISSION | Upper UTC bounds satisfy unchanged source-close/transport/receipt freshness limits at release, not just enqueue. |
| NO_DUPLICATE_ADMISSION | Preserve native session/sequence/fingerprint; atomic exactly-once release through existing continuity owner, with durable recovery handling. Clock proof alone cannot establish idempotency. |
| NO_FABRICATED_BOUNDARIES | Preserve source label/contract/calendar hash; complete contiguous 1m inputs only; never fill gaps or derive bar labels from arrival time. |

The current exporter lacks sufficient monotonic/source provenance for that
proposal. A quarantine/release pipeline would be a separately reviewed change;
this sprint does not implement or authorize it. Existing gate protections are
preserved, not claimed to be absolute external UTC guarantees under arbitrary
host error. Characterization tests explicitly show the distinction: a shared
fast host can pass a near-boundary local comparison, and a slow host can make
an over-age candle look younger. No runtime check is relaxed to hide those cases.

## Current-host adjudication and follow-up

Prior 06:13 UTC low-delay estimates were +136,893 to +138,790 microseconds
reference-minus-host, with active +44.8 ppm correction. They are historical
diagnostics, not new measurements and not proof of a future error envelope.
Reviewed absolute-reference, drift, paired-receipt and operation-window evidence
is missing. All five operation readiness results are UNKNOWN / ineligible.
News remains uncertified; PAPER disabled; SIM unknown/disabled; LIVE absent.

Next step: review a concrete clock-evidence acquisition/provenance and bounded
drift specification, then separately certify operation windows and native
timestamp mapping. Do not repeatedly reinterpret lower NTP offsets as a new
authority, change Windows settings, or arm ingestion on this offline result.

## Verification and preservation

Synthetic tests cover exact host, +/-10/50/100/150/250/1000 ms, and events 1 ms
before, exactly at, 1/50/150/1000 ms after minute boundaries; FORMING, CLOSED,
freshness edges, duplicates, gaps, complete/incomplete HTF, daily/weekly and
synthetic holiday state. Additional tests attack reference independence,
asymmetry, drift, sample age/count/replay, host steps, W32Time state and horizons.
The two-sample minimum never substitutes for a reviewed stability/drift bound.
Native boundary margins remain evidence only. No code, fixture or configuration
changes production=90, paper=80.5, quality=85. No native compilation is needed.

Final validation: the 55-module relevant backend regression passed 1,656 tests;
the final expanded Sprint 15T suite passed 580 tests (counts overlap: the broad
run contained the initial 392 Sprint 15T cases). Frontend dashboard tests passed
32 cases and lint passed. No frontend source/build change was needed. Initial
collection attempts required restoring the existing reviewed test-process risk
profile and private hash-checked dataset mapping; neither runtime configuration
nor datasets were edited. Synthetic fixture date/validation expectations were
corrected before the passing runs. One existing Starlette/httpx deprecation
warning remains. Git diff checks, including the four new files, pass. Reviewed
runtime/native source hashes and all 18 prior native evidence prefixes match;
109 unrelated untracked files remain. No commit or push was requested/performed.

Sources: [Microsoft clock correction/settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings),
[HOLD/SYNC definitions](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-w32t/b4abb4b0-6d6e-41e4-bd41-d54980d0598a),
[clock adjustment API](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeadjustment).
These document platform behavior; they do not attest this host's absolute error.
