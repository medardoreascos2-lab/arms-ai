# Sprint 15W: production emission pairing (offline)

Baseline: `b40a25748fe3a7eb4654109ef3ae68ff9a293edc`, branch
`refactor/backend-architecture`. This sprint adds evidence to
`ArmsReadOnlyMarketV1`; it does not grant clock, market, paper, SIM or LIVE
authority. No production capture was armed during initial implementation. The
subsequently authorized production capture is adjudicated below; its coordinated
closure failed even though the eventual sealed stream has valid timing pairs.

## Scope and provenance

The successful Sprint 15V R4 witness established pairing for its own diagnostic
stream. It cannot timestamp or certify production emissions. Production now
captures its own bracketed QPC / UTC / QPC observations. The callback pair is
sampled immediately after the existing Realtime / primary-series / first-tick
guards and before the lock and metadata reads. A second pair supplies the
**exact** UTC value in that canonical bar record's `event_time`. CLOSED and
FORMING emitted by one callback share the callback pair; they have separate
emission pairs. QPC frequency is serialized, not inferred from Python's clock.

Existing readiness, source checks, connection callback, heartbeat, HELLO,
canonical non-bar serialization and candle construction are unchanged. The
historical Sprint 13 source is preserved verbatim in
`backend/tests/fixtures/ArmsReadOnlyMarketV1.sprint13.cs` and still checked
against its original certificate hash. That certificate remains historical;
it does not silently certify the modified production source.

## Sidecar contract

Canonical `arms.nt.market.v1` retains its six root fields and original bar
payload. Existing consumers need no changes. The new file is inside the
exporter's existing output directory at
`timing/<exporter-session>.production-timing.jsonl`, outside the top-level
canonical `*.jsonl` enumeration. It is created lazily on the first admitted bar.
No file paths or account/provider objects are serialized.

Each sidecar record contains exporter UUID, canonical sequence, contiguous pair
sequence, kind, source close label, callback/emission pairs, bar indexes,
Realtime/series/first-tick flags, and existing NQ/contract/Minute/1/UTC/template
identity. SHA-256 covers the **exact UTF-8 serialized canonical row excluding
its line terminator**. The canonical string is serialized once, written to the
original file, then hashed for the sidecar. The template name establishes the
existing identity only; this change does not acquire the loaded calendar's
contents, session boundaries, or holiday authority.

At the original stop boundary, DISCONNECTED is emitted and canonical and
connection writers are closed. Timing closure then publishes a fully disposed
`.done.json` seal through an exclusive `.done.tmp` file. The seal binds the
complete sidecar byte count, row count and SHA-256 (including every LF), exporter
session, and total canonical count. An exclusive file name prevents replacement.
This is correspondence/integrity evidence, not authenticated attestation.

Any sidecar open/write/hash/pair/closure failure invalidates timing evidence and
prevents a valid seal. It does not stop or admit canonical candles. Canonical
write failures retain the original stop path. No timer, network access, sleep,
connection mutation, account API, or order API is added. Timing failure cannot
produce a positive offline timing result. There is intentionally no new
production timeout or per-session record limit that would alter market behavior.

## Offline adjudication

`tools/production_timing_v1.py:adjudicate` accepts three closed byte streams:
canonical, timing sidecar and seal. It rejects malformed/duplicate-key JSON,
oversize/truncated streams, wrong schema, sequence/session mismatches, wrong
hashes, absent/duplicate/reordered pairs, wrong indexes/labels, historical or
nonprimary callbacks, broken QPC/UTC order and absent writer closure.

Every production FORMING/CLOSED must have exactly one pair. Five contiguous
FORMING observations yield three complete CLOSED observations under the
unchanged exporter startup exclusion. A CLOSED observation must match an earlier
FORMING index and label and the following FORMING callback. Close labels remain
close labels; implied starts are label minus one minute. No runtime candle
timestamp, payload or admission rule is rewritten. The verifier's CLOSED label
check is diagnostic and does not certify absolute UTC accuracy.

PASS means `PASS_STREAM_ONLY`, never freshness, calendar admission, reference
accuracy or drift authority. The verifier is intentionally bounded to 256 rows
per stream and 2 MB, suitable for the proposed short capture, not arbitrary
production archives. It imports no execution service and starts no watcher.

## Clock evidence binding design

The explicit `acquire_clock_measurement` function wraps a Clock Evidence V1
probe with Windows `QueryPerformanceCounter` observations before and after the
entire probe, with a two-second probe timeout. It is never called by the exporter,
adjudication, imports, or this sprint's tests except through synthetic doubles.
Use Clock Evidence's bounded allowlisted resolver beforehand.

A future acquisition must use one fresh run UUID as the reference measurement
`epoch`. Preserve raw probe JSON, its SHA-256 and both QPC brackets. The
`clock_epoch_binding` function binds those bytes, epoch, exporter UUID, canonical
and sidecar hashes, frequency and conservative sample-age envelopes. It requires
ordered measurements before the first production callback and after the last
emission. It labels later measurements unavailable at the last emission; these
cannot retroactively become online authority. Python `perf_counter_ns` values
are never relabeled as native QPC ticks.

The wrapper preserves Clock Evidence's raw uncertainty and observed drift
measurements. `reference_uncertainty` and `reviewed_drift_rate` remain null until
independent review establishes conservative bounds. Public NTP consistency,
nominal Windows clock adjustment, low round-trip time and UTC/QPC agreement do
not establish either bound. The manifest is correspondence only: probe validity
must still be checked by Clock Evidence V1, and operation windows, a reviewed
calendar, reference bounds, rate bounds and freshness must still be supplied to
Clock Preflight V1. With absent reviewed bounds, preflight remains UNKNOWN and
all clock-ready flags remain false. Windows configuration is never changed.

## Validation and limits

The certification JSON records the test run and source hashes. Tests compile
both the historical and updated whole exporter against the same synthetic host,
using identical deterministic clock/UUID inputs, and compare canonical and
connection bytes across startup, successful bars, connection failures, normal
stop, reentry and sidecar I/O failures. Independent process sessions cannot mix
seals or streams. Existing canonical reader regressions are retained.

The modified source is compiled against the installed NinjaTrader SDK without
loading a provider or touching the installed user script. The IL audit allows
only the same 18 Cbi metadata getters; no account/order method is reachable.
Local synthetic benchmarking uses three 1,000-callback trials per exporter
(1,998 bar records each). The measured additional per-record cost is recorded in
the certificate. This measures local evidence I/O, not real provider latency or
worst-case disk stalls. A broad 20 ms added-average regression ceiling is a test
guard only and does not modify ARMS timing tolerances.

## Original bounded capture plan

This plan required operator replacement and compilation of **ArmsReadOnlyMarketV1**.
The operator subsequently reported completing that step before the authorized
capture. No NinjaTrader copy was installed or manipulated by the agent.

The shortest useful capture ends after three validated complete CLOSED bars and
their associated FORMING callbacks: five consecutive admitted first ticks,
normally about 240–300 seconds after readiness. Allow up to **330 seconds from
fresh exporter start**, including the existing 30-second startup allowance.
Use a fresh isolated production-exporter instance/output directory on the
already approved NQ DEC26 Minute/1 UTC / CME US Index Futures ETH setup; do not
reuse any R4 witness rows or old exporter prefix.

Before activation, a separately authorized bounded coordinator must verify the
reviewed source hash, empty fresh directory, new run UUID, Windows QPC frequency
and a starting clock-reference measurement. A 600-second manual activation
allowance is reasonable. Collect clock probes at a bounded cadence through the
capture in the coordinator, never in NinjaTrader. At target completion or the
330-second acquisition deadline, stop collecting and request normal operator
removal of that isolated exporter to exercise its existing close path. Allow
30 seconds for operator closure and 10 seconds for final bounded reference
measurements: **370 seconds maximum from exporter start**. Missing closure or
insufficient CLOSED bars is incomplete evidence, never success. The unmodified
production exporter does not automatically stop when a collector times out.

Archive fresh source identity, coordinator start/end QPC receipts, raw clock
probes/bridges, read-only Windows clock observations, canonical stream, sidecar,
seal and reviewed calendar binding. The coordinator must verify freshness and
single-session membership separately from the offline byte-stream verifier.
The private coordinator was subsequently prepared under separate explicit
authorization, tested, and started once. It has now exited; no replacement is armed.

Offline readiness is conditional on the reported green checks. Immediate native
activation and live analysis remain NO. A production pairing result cannot resolve
absolute reference/drift authority without independently reviewed evidence.

## Recorded production capture adjudication

Run `3e821985-2bcd-4ccc-adef-3cb588cbeb61`, watcher
`58a2fc6f-f981-4615-8d5b-56b508669811`, exporter session
`f36aeebc-0ca7-4079-a318-55cce9d38602`.

**Production emission pairing passes for the recorded stream. The coordinated
capture is incomplete.** The watcher terminal result remains
`FAILED / WRITER_CLOSURE_TIMEOUT`; it must not be replaced by a retrospective PASS.
The watcher process exit and current exclusive read access to all four native
files were independently verified. The receipt contains first observation but no
seal observation or final reader QPC bracket.

The first file observation was `2026-09-21T15:06:47.776489Z`. HELLO was emitted at
`15:06:52.7417479Z`; DISCONNECTED / `TERMINATED`, error `NONE`, was emitted at
`15:16:20.5468832Z`. HELLO-to-END is **567.8051353 seconds**. First-observation
paired UTC-to-END is about **572.770 seconds**. The declared closure deadline was
`15:12:47.776489Z`; the recorded termination was about **212.770 seconds late**.
This differs from the operator's approximate 5m30s description. The reason for
that discrepancy is not established. QPC independently proves emissions continued
more than three minutes beyond the watcher's terminal monotonic timestamp, so this
is not inferred solely from an absolute UTC comparison.

The sealed stream has 134 canonical records: one HELLO, 114 HEARTBEAT, ten FORMING,
eight CLOSED and one DISCONNECTED. All 18 bar records have exactly one matching
sidecar entry. Canonical sequence 0–133 and pair sequence 0–17 are contiguous;
malformed, duplicate, missing-pair and out-of-order counts are zero. The seal's
session, 18 records, 16,672 bytes and SHA-256 all match. The canonical stream is
27,069 bytes. Hashes:

- Canonical: `69d3e5685633af8c3bde3dba3bc52876905856d46c4a2e37df63b99e9f1d8e5d`
- Sidecar: `86269e651e16e63e4cee8579016e96893adfd6c89e569fcb1c511d5e911ffe82`

The existing reader's actual frame parser also accepts the recorded HELLO,
heartbeat and candle frames in a test-only historical replay with an inert sink,
then rejects DISCONNECTED as expected. This is parser compatibility, not fresh
runtime admission. OHLCV fields, close labels, minute spacing, tick alignment,
Realtime/primary-series/first-tick flags and bar indexes remain valid. The first
two partial/startup closures remain excluded. Existing template identity is
verified; no new loaded-calendar or holiday proof is inferred.

Six FORMING and four CLOSED pairs fall within the first 330 seconds. Eight later
pairs are outside that acquisition window. These distinctions are reported without
truncating the stream, fabricating a replacement seal, or importing R4 witness
evidence. The original 791 acquisition files were hash-frozen before adjudication.
The certificate embeds the recorded canonical stream, sidecar, seal, original
terminal/receipt and all raw clock measurements for deterministic offline replay.
Those fixtures must never be injected into a new capture as fresh evidence.

## Clock observations from this run

All **387 of 387** public reference replies pass independent raw packet replay
through `clock_evidence_v1.decode_reply`; each raw measurement hash and outer QPC
bridge is valid and ordered. The epoch is exactly the capture run UUID. Provider
group names are labels, not proof of reference independence or authentication.
192 samples are wholly inside the first 330 seconds, and 207 inside the 360-second
closure budget. Remaining samples precede native activation.

Positive offset means reference midpoint ahead of host UTC. All samples are
retained; the main medians below do not discard high-delay samples.

| Reference group | Valid | Offset range (ms) | All-sample median (ms) | RTT range (ms) |
| --- | ---: | ---: | ---: | ---: |
| Cloudflare | 129 | -297.416 to 328.423 | 24.865 | 24.957 to 673.268 |
| Google | 129 | -59.848 to 487.405 | 23.865 | 37.446 to 965.265 |
| Microsoft | 129 | -20.113 to 208.627 | 24.612 | 53.396 to 418.754 |

All-sample median disagreement is 1.000232 ms. Clock Evidence's explicitly
descriptive lowest-RTT-half medians differ by 1.6069745 ms; the largest same-round
midpoint disagreement is 386.419981 ms. Neither statistic is an error bound.
Observed host UTC versus monotonic rate is about +21.700 ppm across each reference
series. Observed offset slopes are +25.614, -10.678 and -12.018 ppm respectively;
network asymmetry and reference error remain unresolved. No reviewed drift bound
is derived from those slopes.

Clock sampling spans `15:01:34.837013Z` through `15:12:43.295840Z`. The last outer
clock QPC bracket precedes the final production emission by **196.7828204 seconds**.
The most recent per-reference sample age envelope at that emission is approximately
196.999 s, 196.907 s and 196.849 s respectively. The oldest sample was already
668.404 s old at collection end. There is no post-closure sample or closing Windows
snapshot. `production_timing_v1.clock_epoch_binding` therefore correctly rejects
the full stream with `EPOCH_DOES_NOT_BRACKET_PRODUCTION`.

The initial Windows snapshot reports W32Time Running / Auto, state Sync, stratum 5,
source `time.windows.com,0x8`, and 1849.231 seconds since the last good sync. The
configuration query returned ACCESS_DENIED; last-sync monotonic mapping is absent.
The nominal adjustment observation is +19.2 ppm, not a rate guarantee. No Windows
configuration was changed and no later state is invented.

Clock Preflight was evaluated using the actual measured samples and no reviewed
bounds. It returns `UNKNOWN / REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING`, with all
operation-ready flags false. Reference error and drift bounds remain UNKNOWN.

## Remaining readiness gates

Production emission correspondence is resolved for this recorded stream. Before
fresh NQ can be attached to the dashboard analysis path, establish reviewed
reference-error/drift authority and a complete contemporaneous measurement epoch,
then evaluate existing freshness, loaded-calendar/session and admission gates on
a newly authorized live stream. This terminated archive cannot become current data.
The shortest next step is review of the clock-authority evidence requirements and
the documented closure discrepancy, not another pairing-only witness capture.
Any further coordinated capture needs separate authorization and a seal observed
before the coordinator deadline. No replacement watcher is started here.

Local PAPER entries remain disabled independently by NEWS_UNCERTIFIED. SIM
execution and LIVE broker execution remain disabled. No dashboard stream, account,
order, Windows setting, timestamp tolerance or runtime admission behavior changed.
