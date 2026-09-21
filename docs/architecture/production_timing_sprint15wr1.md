# Sprint 15W-R1: closure and clock-authority review

Baseline `b40a25748fe3a7eb4654109ef3ae68ff9a293edc`, branch
`refactor/backend-architecture`. Offline review only. No watcher, clock probe,
NinjaTrader action, Windows change, execution, or runtime-gate change.

## Preserved finding

Run `3e821985-2bcd-4ccc-adef-3cb588cbeb61`, watcher
`58a2fc6f-f981-4615-8d5b-56b508669811`, native exporter
`f36aeebc-0ca7-4079-a318-55cce9d38602` remains
`PRODUCTION_EXPORTER_EMISSION_BINDING=PASS_STREAM_ONLY` (18 pairs, no missing,
duplicate or reordered pairs; eight CLOSED). This review neither invalidates that
finding nor requests another capture to prove the same pairing. Original capture
files, source-at-capture snapshots, receipt and failed terminal remain unchanged.

## Timeline and attribution limits

Times below are host UTC observations, not independently certified absolute UTC.
Filesystem times share the host wall clock and are corroborating metadata, not a
separate UTC authority or a timestamp of the operator action. QPC supplies the
independent elapsed-time cross-check. The original watcher and coordinator are
the same process/control loop; their monotonic readings are not two independent
instruments. Only initial verification and final status survive, not a continuous
append-only heartbeat history.

| Event | Available observation | Meaning / limitation |
| --- | --- | --- |
| Initial clock sample | 15:01:34.837013 UTC | Before native activation |
| Waiting/activation gate | 15:01:35.216629 UTC; QPC 8724977698372..8387 / 10,000,000 | 600-second allowance; display deadline 15:11:35.216629 |
| Independent waiting check | About 15:01:52 UTC; heartbeat counters 81,84,87,90 | Empty inbox, advancing process verified before activation |
| Canonical file creation | 15:06:47.732912 UTC filesystem | File opened at realtime startup, before HELLO |
| First watcher observation | 15:06:47.776489 UTC; QPC 8728103229136..9157 | Activation was within allowance; native observation starts here |
| HELLO | 15:06:52.7417479 UTC | Startup readiness completed; not the initial activation instant |
| First paired callback | 15:07:00.0621936 UTC | First eligible production bar callback |
| Capture-complete threshold | First observation +330 monotonic seconds | Original loop changes a status field; no recorded visible prompt/ack |
| Final clock receipt | 15:12:43.295840 UTC | 387 valid measurements total; no post-closure sample |
| Closure deadline | First observation +360 monotonic seconds; display equivalent 15:12:47.776489 UTC | Actual enforcement uses `time.monotonic()`, not UTC |
| Watcher timeout | `capture_elapsed_seconds=360.0211212000577`; final heartbeat monotonic 873170.3482176 | FAILED / WRITER_CLOSURE_TIMEOUT, counter 3157 |
| Terminal/result files | 15:12:47.806149..811400 UTC filesystem | Terminal publication follows timeout; exact timeout instruction not separately timestamped |
| Final paired emission | 15:16:00.0824257 UTC; QPC 8733626174767..4771 | 192.2945635 QPC seconds after first-seen +360; about 192.269 s after terminal heartbeat |
| Canonical END timestamp | 15:16:20.5468832 UTC, DISCONNECTED / TERMINATED / NONE | UTC sampled inside Emit, before serialization/WriteLine; not callback-entry time |
| Canonical last-write metadata | 15:16:20.5468832 UTC | Consistent with END; does not measure WriteLine duration |
| Seal creation / last-write metadata | 15:16:20.5483831 / 15:16:20.5491336 UTC | Temp-file creation/last write preserved by rename; publication instant not separately instrumented |
| Watcher's first seal observation | Absent | Watcher had already failed/exited; no reader_end receipt |

The approximately **212.770279 seconds** is END sampled UTC minus first-seen
paired UTC minus 360 seconds. Using the first-seen display string differs by
0.0001152 seconds. It is not a measured remove-to-callback delay. The seal metadata
follows END by about 1.500/2.250 ms; these are wall-time differences, not upper
bounds on publication or visibility. Canonical duration HELLO-to-END is
567.8051353 seconds; first-seen paired UTC-to-END is 572.770279 seconds.

The exact split remains unavailable:

- OPERATOR_REMOVE_TIME: not recorded. No inference that the operator acted late.
- NINJATRADER_TERMINATION_CALLBACK_TIME: entry not recorded. END's TERMINATED
  branch demonstrates termination handling occurred, but OnStateChange first
  acquires `sync`; Stop also detaches timers/prints before Emit. Queue/lock/work
  delay cannot be quantified from these files.
- CANONICAL_END_WRITE_TIME: pre-write UTC observation plus filesystem metadata;
  exact write start/completion not recorded.
- TIMING_SEAL_WRITE_TIME: filesystem metadata only; exact rename/visibility QPC
  absent. Complete hash-valid contents prove eventual closure, not timely closure.
- WATCHER_FIRST_SEAL_OBSERVATION: none; failed receipt cannot be supplemented
  retrospectively with a synthetic observation.
- WATCHER_TIMEOUT_TIME: demonstrated at >=360 monotonic seconds, with ~21 ms
  polling overshoot, consistent with the existing contract.

Root-cause classification: **UNRESOLVED**. OPERATOR_TIMING,
NINJATRADER_CALLBACK_DELAY and delay inside termination handling remain hypotheses.
FILESYSTEM_VISIBILITY_DELAY alone cannot explain callbacks/emissions continuing
after timeout. No WATCHER_DETECTION_ERROR, COORDINATOR_DEADLINE_ERROR or
CLOCK_DOMAIN_MIXING is demonstrated: the loop uses one monotonic basis for elapsed
budgets; raw QPC agrees on the long overrun. Publication latency cannot explain
~213 seconds. Current filesystem observations cannot reconstruct missing UI events.
No broader account-bearing NinjaTrader logs were read.

## Revised offline closure contract

A 30-second manual-removal deadline is **not required by production pairing**.
Pairing requires a complete closed canonical stream, sidecar and valid seal.
Bounded acquisition and complete clock coverage are separate requirements.
Late closure still fails the original run; this review never changes its budget.

`tools/production_capture_contract_v1.py` implements a new pure transition engine:

1. WAITING_FOR_ACTIVATION only after adapter verification of pre-activation clock
   samples, source hashes, process identity and empty fresh inbox.
2. CAPTURING from first observed fresh session; after 330 QPC seconds require at
   least three CLOSED observations and publish CAPTURE_COMPLETE_REMOVE_REQUEST.
3. REMOVE_REQUESTED has a unique run-bound request ID. A visible local operator
   panel must show the specific isolated instance, elapsed time and remove action.
   Record acknowledgment of that request. An acknowledgment is not proof of a
   remove click; those must remain different fields.
4. WAITING_FOR_CLOSURE starts its 30-second monotonic allowance **at acknowledgment**,
   with a visible countdown and durable QPC request/ack/deadline journal. A late or
   unacknowledged seal never silently passes. Retain conservative deadline-first
   checking; a first observation at/after deadline fails even if disk timestamps
   appear earlier. Actual operation/visibility attribution stays separate.
5. FINAL_CLOCK begins only after complete seal adjudication, matching exporter
   identity, raw QPC containment and independently checked exclusive closure.
   The adapter keeps collecting through this stage, rechecks unchanged closed
   file hashes, and obtains valid probes starting after seal observation for
   **every configured reference**. Only then COMPLETE / PASS_COVERAGE_ONLY.

Proposed operational budgets: activation 600 s, acquisition 330 s, request
acknowledgment 60 s, acknowledged closure 30 s, final probes 30 s. The added
acknowledgment and final-probe budgets are explicit proposed operator allowances,
not new timing tolerances or error bounds. Maximum ready-to-finish budget is
1050 s, plus separately bounded collector initialization. Missing acknowledgment,
seal, target, collector, epoch continuity or final probes latches failure. An
invalid stream cannot become valid by waiting longer. Early removal is preserved
as a failed coordinated capture, although a separately adjudicated sealed prefix
may retain stream-only pairing proof.

The old private live coordinator is preserved, not overwritten. The R1 engine
has no I/O or entry point and cannot arm anything. The live operator panel,
durable journal and adapter integration remain an explicit **pre-activation
delivery requirement**; this sprint returns the offline contract and plan first.
No claim of tested native UI delivery or a launch-ready watcher is made.

Adapter contract: one new run/session, exclusive fresh paths, source hashes,
one unchanged Windows boot/QPC-frequency epoch; snapshot and request publication
must be durable before being offered to the operator. In a future run verify
multiple live advancing status heartbeats and visible panel delivery. Require
fresh collector health (retain existing 20-second health lease), bounded probing
and parsing, 1000 clock records / 256 canonical records / existing byte limits.
Do not acknowledge automatically or use filesystem wall timestamps as proof of
operator receipt. UI/publisher failure must fail within the 60-second allowance.
Persist operator-reported removal separately with a QPC receipt and explicitly
label it as reported, never as NinjaTrader callback instrumentation.

## Clock coverage design

All reference probes retain raw packets, before/after Windows QPC brackets,
frequency, epoch and exact measurement hashes. Never equate arbitrary Python
perf_counter epochs with .NET QPC by relabeling integers. Keep the existing
bracketing API. Before activation, every selected reference must have valid
samples; continue through observation, remove request, acknowledgment, closure
and final probes. Acquire a closing Windows snapshot and QPC-correlated state.

The new coverage function replays every retained packet, reuses
`production_timing_v1.clock_epoch_binding`, requires per-reference pre-first-pair
samples and post-observed-closure samples, and rejects an event after the final
sample. This stronger closure coverage implies all included production pairs
are inside the supported capture epoch. Continuous collector health and reviewed
sample-age/drift validity remain additional adapter/authority requirements; two
endpoint samples alone are not drift authority. On any bounded timeout, stop
collection with a failed terminal; never wait indefinitely for a missing seal.

The old run still returns EPOCH_DOES_NOT_BRACKET_PRODUCTION. Its last clock bracket
ends 196.7828204 seconds before the final paired emission. R1 synthetic coverage
tests do not extend that real epoch or fabricate real samples.

## Exact clock authority requirements

`clock_preflight_v1.ReviewedBounds` requires epoch, valid_from_mono_us,
valid_until_mono_us, rate_error_ppb, capture_error_us, references and review
provenance. Each ReferenceBound requires reference, independence_group, error_us
and provenance. At least **two independently reviewed groups**, each with two
distinct samples, are required. Public provider labels are not independence
attestation. A provenance string is an audit reference, not signature validation.

Let D(t) = ceil(abs(t_us) * rate_error_ppb / 1e9), E = reviewed reference error,
P = capture_error_us, d = monotonic round trip, a = age since receipt. The existing
receipt enclosure is [reference_send - E - P,
reference_receive + d + D(d) + E + P]; propagation adds a and expands both ends
by D(a) + 2P. All intervals must have a nonempty common intersection, but the
reported result is their conservative **hull**, not their intersection/median.
Project the upper endpoint by horizon + D(horizon), then require the whole
interval to lie within the reviewed operation window with its endpoint policy.

There is **no fixed maximum-sample-age parameter** in the existing assessor.
All sample times and the decision/horizon must lie inside bound validity. Age
expands uncertainty and may make window containment fail. A reviewed acquisition
plan must state its maximum permissible age, derived from those validity limits
and operation-window margin, not from the observed median or a favorable guessed
constant. An external contractual age ceiling would need an explicit adapter
check; it is not silently enforced today. No runtime tolerance is changed here.

| NAME | DEFINITION / UNIT | SOURCE OF AUTHORITY / HOW DERIVED | VALIDITY WINDOW / MAX SAMPLE AGE | DRIFT PROPAGATION / FAIL-CLOSED |
| --- | --- | --- | --- | --- |
| REFERENCE_SERVER_ABSOLUTE_ERROR_BOUND | Maximum absolute server UTC timestamp error E, microseconds | Traceable documented endpoint/service uncertainty, authenticated endpoint identity, leap/smear timescale and upstream independence reviewed for this epoch. No such evidence is in this archive. Root dispersion alone is not independently attested authority. | Provider uncertainty validity plus reviewed epoch; samples must be inside both. Age cannot exceed review validity or window-derived limit. | Add E at acquisition and D(a) later; unknown source, expired assurance, changed timescale or unauthenticated identity prevents promotion. |
| NETWORK_ASYMMETRY_BOUND | Interval uncertainty from unequal one-way delays, microseconds | Existing model permits all measured RTT on either nonnegative path, conditional on trusted reference timestamps and bounded local rate/capture error. No symmetric-route assumption. A tighter bound requires independent path calibration. | Per exchange; no transfer of a favorable low-delay sample to another packet. Same reviewed epoch/age rule. | Use full causal interval, D(d), then D(a). Invalid order, reference duration exceeding round trip, broken trust or interval too wide fails. Finite conditional RTT envelope exists; unconditional absolute authority does not. |
| MEASUREMENT_ERROR_BOUND | Maximum timestamp quantization/read/correlation error P, microseconds | Reviewed acquisition API/OS/hardware resolution, rounding, scheduling brackets and cross-domain correlation. Serialized 100 ns digits/QPC frequency alone do not prove precision or accuracy. No host-specific reviewed P supplied. | Exact build/platform/epoch and measured bracket assumptions; age rule from validity/window. | Existing assessor adds P at receipt and 2P during propagation; wall-vs-monotonic consistency must fit D(elapsed)+2P. Exceeded bracket, changed API/platform, unknown mapping or step fails. |
| HOST_DRIFT_BOUND | Bound on BOTH monotonic rate error relative to true elapsed time and host-wall/monotonic drift; ppb | Independent calibrated/reference-supported oscillator and host slew/holdover specification over environmental/OS conditions, with step detection. Observed ~21.700 ppm and nominal +19.2 ppm are not worst-case guarantees. | Explicit monotonic validity endpoints, covers samples, now and horizon; max age limited by derived interval margin. | D(t) outward rounding above. Rate must be nonnegative and <1e9 ppb. Changed boot/frequency, unexplained step, expired qualification or missing evidence fails. |
| REFERENCE_DISAGREEMENT_BOUND | Consistency of independently justified UTC intervals, microseconds | Derived from E/P/RTT/rate envelopes for each source. Current code has no separately configurable median-disagreement threshold. ~1 ms agreement can share common-mode error. | Same epoch and propagated decision instant; every retained sample must remain valid. | Require max(lower) <= min(upper), retain full hull. Disjoint intervals fail; no outlier deletion, majority vote or favorable threshold. Numeric authoritative disagreement bound remains unavailable while constituent bounds are missing. |

Other missing inputs: independently mapped `WindowsState.last_sync_mono_us`,
observed_mono_us, healthy Running/Automatic state, Sync/Hold, last_error=0 and
source in the reviewed reference set. The initial snapshot has no monotonic
last-sync mapping; configuration access was denied and no closing snapshot was
captured. Naively subtracting a wall-time last-sync age is not that mapping.
Each MARKET_ANALYSIS window also needs reviewed provenance for the intersection
of freshness, minute/session/calendar and horizon constraints. `bounds=None`
returns UNKNOWN before any later condition can grant readiness.

## Smallest alternative evidence architecture

The present plain internet-NTP method cannot supply an authoritative finite
absolute UTC bound by itself. More identical captures only add observations.
The smallest change to the evidence path is an authenticated acquisition adapter
for at least two independently justified time references whose endpoint error
envelopes and timescales are reviewable, together with a qualified local
capture/rate envelope and mapped Windows synchronization state. This need not set
the Windows clock, but no suitable authority source is established here.

NTS adds identity/integrity; it does not itself certify server UTC accuracy or
eliminate asymmetric delay. The current 48-byte parser rejects extensions, so
NTS is a separate reviewed adapter change, not a configuration toggle. If public
services cannot provide reviewable error assurances, use a calibrated local
UTC-traceable timing appliance/PPS or hardware timestamp source with an
independent cross-check and documented delivery/holdover uncertainty. One GPS
receiver alone does not satisfy the current two-independent-reference contract.
Hardware is a conditional alternative, not a purchase recommendation.

Compatibility constraint: the unchanged assessor also requires the Windows
configured source to be in the reviewed reference set. Adding two authenticated
external sources while leaving `time.windows.com` unreviewed does not satisfy
that gate. The evidence route must cover the existing Windows source and last
sync mapping, or a separately authorized architecture review must change how
external UTC evidence is consumed. No such change is made or assumed here; there
is no established drop-in authority source that makes the current run ready.

Primary references: [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html) describes
NTP dispersion and synchronization distance under its clock model;
[RFC 8915 section 8.6](https://www.rfc-editor.org/rfc/rfc8915.html#section-8.6)
explains why authentication does not remove packet-delay asymmetry;
[Microsoft QPC guidance](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)
distinguishes elapsed QPC time from external UTC synchronization. These documents
do not constitute a calibration certificate for this machine or these endpoints.

## MARKET_ANALYSIS dependency matrix

Read-only source review, not a proposal to enable runtime admission. Scope is the
current native-reader/current-candle/dashboard analysis path and its analysis
validator dependencies; execution authorization remains separate.

| Property / source location | Existing time dependence | Source labels + monotonic alternative | Absolute UTC still needed? |
| --- | --- | --- | --- |
| Record identity, duplicates, order; reader `_frame`, current authority `admit` | UUID/sequence/hash plus wall-event nonregression | Session, canonical sequence and exporter callback/emission QPC prove same-host ordering; no wall offset needed | No for ordering alone; restart/epoch and source identity still mandatory |
| Transport emission-to-receipt age; reader `_frame` | now - event_time, bounded by heartbeat deadline | Bind canonical row to emission QPC and receipt QPC in same boot; elapsed-time/rate bound; reject backlog/replay | Absolute offset is avoidable for this local leg; sidecars currently cover bars only, not HELLO/HEARTBEAT |
| Heartbeat/liveness; reader `poll`/`get_snapshot` | now - last_received, wall clock | Receiver monotonic last-receipt age, rate-qualified timeout, epoch reset fail-closed | No for liveness alone; liveness does not establish market freshness |
| Local received-to-decision age; current authority `admit` | now - received_at | Monotonic receipt/decision pair | No for elapsed local age, with persistence/restart rules |
| FORMING/CLOSED current-market age; authority `admit`/`age_seconds` | emitted vs label/start/close; now - close | Labels establish minute identity and subsequent callback establishes local completion ordering. Monotonic residence measures only local delay | Yes or equivalent independent bounded source-time-to-real-time anchor. A newly emitted stale/replayed source bar can have fresh local QPC |
| Bar completeness / HTF; `ClosedBarAggregatorV1.update_completed` | Source Chicago/UTC labels, full minute buckets and chronology | Already event-driven; source labels, complete constituent bars and sequence suffice after upstream admission | No new host UTC proof for aggregation; DST/calendar/source semantics remain necessary |
| Contract validity / historical session membership; authority `admit`, `_gap_proven_closed` | Label interval in contract validity and certified schedule | Reviewed source labels/calendar establish membership of those bars | No host-now UTC needed for membership alone; cannot infer present market state |
| Market open NOW / reopening; `SessionStateAuthorityV1.resolve`, current service snapshot | Current UTC mapped to certified exchange calendar | A qualified UTC anchor plus monotonic propagation can replace repeated wall reads, but cannot remove the anchor | Yes near open/close/holiday boundaries, or independently bounded exchange-current-time authority |
| Analysis signal age; `LiveMarketAnalysisService._calculate_signal_age_seconds` | datetime.now - analyzed_at; analyzed_at derives from last candle timestamp | Local computation TTL can be monotonic; source-bar age still needs its anchor | Split computation age from market-data age; replacing one does not resolve the other |
| Spread/quote freshness; analysis validator `get_spread_points(now=...)` | Host now and quote timestamp authority | Same-host reception age can use monotonic time; independently sourced quote timestamps require source linkage | Local age can avoid offset; source currency cannot be inferred from receipt alone |
| Calendar query on analyzed candle; analysis `market_is_open` | candles[-1].timestamp | Source-label calendar membership suffices for that analyzed candle | Does not prove market open now; retain separate current-session gate |
| Audit/persistence/cross-host chronology | Wall timestamps, process/session identities | Same-epoch QPC ordering works locally only | UTC/source-time linkage needed across boot/host boundaries; retain both domains |
| NEWS/PAPER restrictions | External event-time windows and certification | Monotonic TTL may propagate a qualified anchor | Separate external-calendar/news authority remains required; NEWS_UNCERTIFIED unchanged |

Evidence locations: `backend/market_data/ninjatrader_market_reader_v1.py`,
`backend/market_data/current_candle_authority_v1.py`,
`backend/market_data/session_state_v1.py`,
`backend/backtesting/current_paper_runtime_v1.py`,
`backend/backtesting/closed_bar_aggregator_v1.py`,
`backend/services/live_market_analysis_service.py`, and the existing
`tools/clock_preflight_v1.py:boundary_proof/assess` /
`tools/clock_evidence_v1.py:analysis_window` sufficient-condition models.

Conclusion: absolute host UTC is over-specified **for pure local elapsed-time and
ordering properties**, but not for proving proximity to exchange/calendar time.
A constant common wall offset cancels in same-host differences; wall steps do not.
No such alternative is wired or authorized in runtime by this sprint.

## Exact next plan and gate

First review the bound-authority evidence route and deliver/review the visible
adapter around the tested offline engine. No capture is useful merely to repeat
pairing. A later, separately authorized readiness-oriented run needs fresh UUID,
isolated paths, the unchanged exporter hash, pre-activation clock/state evidence,
visible acknowledged remove request and the operational budgets above; preserve
all rows through seal, collect final reference probes after observed closure,
then evaluate full-stream coverage and reviewed bounds. Any failure stays failed.

Until those prerequisites and new authorization exist: READY_FOR_NEXT_PRODUCTION_CAPTURE=NO,
READY_FOR_LIVE_MARKET_ANALYSIS=NO. No operator native action is requested now.
