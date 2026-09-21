# Sprint 15V: minimal native timing provenance witness

Baseline: `72a8832943d2d5d69a09e0dd3dcee6d1e6d9115d`.

## Final R4 native capture adjudication

**PASS for the bounded diagnostic witness stream only.** The fresh run
`0e05e4d4-57eb-415f-981f-3f6b3c4ff998`, watcher
`d87bde3a-fbea-4ac9-af77-b813ea242652`, produced native session
`ca149956-c358-4d85-b5b2-c7a2961e0afd`. No other run supplied fresh evidence.
The watcher stopped COMPLETED/PASS and its exact process identity is no longer
alive. Status and terminal records agree, receipt identity/source hash matches the
plan, and independent replay exactly reproduces the saved watcher result. The
inbox contains only this native stream and its matching seal; stderr is empty.

HELLO was recorded at `2026-09-21T13:47:45.0996439Z`; END at
`2026-09-21T13:52:00.1134299Z`. HELLO-to-END QPC duration is **255.0116471s**,
native-start-to-END is 255.0201272s, and recorded host-wall duration is
255.0137860s. These are recorded local clock observations, not certified absolute
UTC. Activation began 108.9009621s after reader start, within the 600s allowance.
The native witness stopped early on **BOUNDARIES_COMPLETE**, as designed.

There are 14 records, sequences 0–13: HELLO, REALTIME, two CONNECTION_EVENTs,
BASELINE, five FORMING, three CLOSED, END. No malformed or duplicate records were
found. The 23,792-byte stream SHA-256 is
`1c4d563074886224dda99f156c2352c3eec3d5b87d6bfcf8b6962c4a0629e4bb`.
The seal binds the byte count, hash, run, session, 14 records, terminal reason,
writer closure and timer detachment. Both files also reopened for exclusive
read access. Original run artifacts were hash-checked before and after analysis.

| Record | Event Status / PriceStatus | Previous Status / PriceStatus | Pinned source Status / PriceStatus, before and after | Transition / decision |
| --- | --- | --- | --- | --- |
| 2, event 0 | Connecting / Connecting | Disconnected / Disconnected | Connected / Connected | PRE_BASELINE → WAIT_ALIGNMENT; WAIT_STARTUP_ALIGNMENT |
| 3, event 1 | Connected / Connected | Connecting / Connecting | Connected / Connected | WAIT_ALIGNMENT → WAIT_ALIGNMENT; CONTINUE |
| 4, independent poll | Not another connection event | Not applicable | Connected / Connected | WAIT_ALIGNMENT → BASELINE_PROVEN |

Both events identify the same pinned source, valid stable snapshots and Realtime
state, with `baseline_established=false` and `bar_evidence_emitted=false`.
The BASELINE record explicitly binds event sequence 1. Its callback QPC starts
5.0003855s after that event's emission; baseline emission is 5.0207090s after
Realtime entry, inside the 30s startup limit. The independent poll confirms
stable Connected channels, source/config validity and calendar hash. **Zero bars
precede proof**, including by callback-entry QPC. END plus verified closure
establishes STOPPED. No reconnect or post-baseline failure occurred in this run;
negative regressions continue to verify their terminal behavior.

FORMING indices are 5088–5092. The first anchor remains excluded from CLOSED
admission. The three complete CLOSED bars are:

| Native bar index | Implied start UTC | Close label UTC | Callback index |
| --- | --- | --- | --- |
| 5089 | 2026-09-21 13:49:00 | 2026-09-21 13:50:00 | 5090 |
| 5090 | 2026-09-21 13:50:00 | 2026-09-21 13:51:00 | 5091 |
| 5091 | 2026-09-21 13:51:00 | 2026-09-21 13:52:00 | 5092 |

Each CLOSED and following FORMING record share the exact callback UTC/QPC pair;
each emission has its own ordered QPC/UTC/QPC bracket supplying its event_time.
Local UTC is nondecreasing and QPC progresses. Equal host UTC timestamps on
separate emissions are not duplicate records or proof of absolute accuracy.
All bars are Realtime, first-tick, primary series, NQ DEC26 Minute/1, Provider31,
UTC application timezone and CME US Index Futures ETH. Native labels, indexed
labels, close-minus-one-minute starts and consecutive indices agree. Trading day
is 2026-09-21; session bounds are 2026-09-20 22:00:00Z to 2026-09-21 21:00:00Z.
Calendar hash `df197dc6184107a0f2f79d806174ceb5bbe7bf23a7ce5a19bedb262fd313a74f`
matches HELLO, the independent poll, every observation and reviewed loaded
calendar/session verification.

The capture closes **R4 startup-event alignment and paired native bar timing for
this diagnostic stream**. `native_timing_witness_v1.adjudicate` returns
PASS_WITNESS_STREAM_ONLY and supplies eight outward-rounded QPC/UTC adapters.
For all eight, `clock_preflight_v1.assess` still returns UNKNOWN with
REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING and every operation false.
`clock_evidence_v1.native_candidate_proof` returns UNKNOWN for production-exporter
binding: this sibling indicator does not establish the production exporter's
own callback/emission instant, and no reviewed absolute intervals are supplied.
No old NTP sample or empirical slope has been promoted to an error/drift bound.

The portable certification embeds the exact hash-bound native JSONL, seal and
receipt for offline regression replay. That historical fixture is never treated
as a new runtime capture. New tests preserve its positive trace and reject removal
of baseline, wrong aligned event, callback before proof, corrupted UTC pair,
duplicate CLOSED payload, foreign run and unclosed writer. They also enforce the
separate production-emission and absolute-clock blockers on the actual pairs.

Only Sprint 15V tests, certification and documentation changed during this
adjudication. Native witness, reader, exporter, Windows settings and runtime
timing/admission/news policies are unchanged. No new watcher, R5, commit or push.
No further diagnostic capture is requested. The next scoped design/evidence step
is to establish pairing for the **exact production exporter records**, with
separate reviewed reference-error and drift/capture-error bounds plus valid
same-epoch operation windows. This requires explicit approval for any exporter
change; it is not authorized by a diagnostic PASS. Market analysis and paper soak
remain blocked; SIM/LIVE authority remains disabled.

Final adjudication validation passed **1,216 tests across 25 modules**, including
all **139 Sprint 15V tests** and the nine new actual-capture replay, corruption
and authority-separation cases. This run includes Sprint 11T startup/readiness,
Sprint 13 market-open/native/calendar certification, Sprint 15T/15U, connection
observer, market data, freshness, session and HTF coverage. Exact selection:
`.arms-dev/sprint15v/r4-regression-modules.json`; result:
`.arms-dev/sprint15v/r4-adjudication-regression.xml`. The installed-SDK compile
and compiled Cbi getter allowlist also passed. One existing Starlette/httpx
deprecation warning remains. `git diff --check`, including the five untracked
Sprint 15V files, passes. All 109 unrelated files, 16 datasets, 18 native evidence
prefixes and the original R3/R4 artifacts remain unchanged. No staged or tracked
modifications; proposed commit scope remains the five Sprint 15V files only.

## Recovery audit and shortest remaining path

Recovery found completed finalization, not a partially executed test suite: the
saved JUnit report parses completely and records 1,216 passing cases, including
139 Sprint 15V cases. All nine focused `actual_r4` fixture cases passed again in
`.arms-dev/sprint15v/r4-recovery-fixture.xml`. The certification JSON, embedded
fixture, private adjudication, receipt and seal parse completely and their
original hashes agree. No incomplete temporary files exist in the run directory.
The watcher is stopped and its original process has exited. Branch and committed
HEAD match the requested baseline; staged and tracked-modification counts are
zero. Legitimate tests/certification/documentation finalization was retained.
The source and reader remain unchanged. No capture was repeated or watcher armed.

The shortest-path decisions are:

| Option | Decision | Basis |
| --- | --- | --- |
| A: Prove production binding solely by static comparison | Partial only; insufficient for paired provenance | `ArmsReadOnlyMarketV1.Emit`, lines 158–162, directly serializes `DateTime.UtcNow` into the exact production row. This proves the UTC field's code origin. It has no `Stopwatch.GetTimestamp` bracket or callback-entry pair. Its startup Stopwatch only limits startup uncertainty. |
| B: Minimal exporter-only provenance change | Required for the missing production pairing under the existing contract; not implemented here | Pair the exporter's own callback entry and the **same UTC read used for its exact row**, using QPC before/after. Bind sidecar evidence to native session, sequence and exact serialized row hash. Review sidecar isolation, cleanup and performance without changing market schema or admission policy. |
| C: Reference/drift authority is the only remaining blocker | No | Exact production-row pairing is independently missing. Reviewed absolute reference error, drift/capture uncertainty, current Windows synchronization evidence and same-epoch operation windows also remain required by the clock preflight. |
| D: Another bounded capture is necessary | No repeat R4 diagnostic capture; fresh production evidence is needed after an approved provenance change | Static proof cannot reconstruct missing QPC observations for old rows. Validate the changed production path offline first; its first authorized bounded production acquisition can also gather the required contemporaneous clock evidence, avoiding a separate witness rerun. Do not capture until the reference/bounds acceptance plan is established. |

The common `DateTime.UtcNow` API, shared host process, equal labels and similar
callback code do not establish equal invocation times or a bounded inter-callback
delay. The successful diagnostic trace therefore cannot supply retroactive
production emission brackets. No exporter change is included in Sprint 15V.

Next action: review a narrowly scoped production-emission provenance and clock
authority evidence plan, with explicit approval before implementing that exporter
change. Then perform offline tests and use one necessary fresh production
acquisition for runtime validation and contemporaneous clock evidence. A public
NTP offset or empirical rate alone is not a reviewed error/drift bound. No Windows
or tolerance change is proposed. R4 needs no further operator action or recapture.
PAPER entries additionally remain blocked by NEWS_UNCERTIFIED.

## R4 startup contract (offline implementation history)

R4 adapts the certified Sprint 11T event-then-poll admission architecture. It does
not declare the R3 Connecting callback harmless, stale, replayed or disconnected.
The demonstrated defect was applying post-readiness continuity requirements before
there was a readiness baseline. An all-Connected event alone also previously
granted R3 baseline, unlike the certified exporter's separate poll.

| Behavior | Certified production exporter (11T, retained by 13) | R3 diagnostic witness | R4 diagnostic witness |
| --- | --- | --- | --- |
| Realtime entry | Starts selection, files and 30s startup deadline | Writes REALTIME after DataLoaded initialization | Retains diagnostic DataLoaded HELLO; starts 30s admission deadline at REALTIME |
| Source selection | Exactly one registered futures source, pinned object, expected provider | Same selection, initial current Connected snapshot | Same selection, both current channels/provider read twice; no disconnected extra feed ignored |
| Subscription ordering | Host-managed indicator override; no global event subscription | Same override; observation begins after DataLoaded pin | Same override; historical alignment cannot qualify for realtime proof |
| Connecting event | Recorded WAIT_STARTUP_ALIGNMENT if known, stable, correct source and no loss/regression | First non-Connected current status terminates | Same certified quarantine; recorded WAIT_ALIGNMENT, zero bars |
| Connected event | Latches alignment, permits previous Connecting/Disconnected only while STARTING | Requires all four current/previous enums Connected; immediately proves baseline | Latches aligned event sequence; never proves baseline itself |
| Independent validation | Dispatcher heartbeat revalidates source at 5s cadence | None between aligned event and baseline | Dispatcher poll revalidates source/config/calendar at 5s cadence |
| READY transition | Aligned event plus later healthy poll before startup deadline | Inside qualifying connection callback | Explicit BASELINE record after aligned event plus separate healthy poll |
| HELLO / heartbeat | Market HELLO and heartbeat withheld until READY | Early metadata HELLO, no heartbeat | Early **diagnostic-only** metadata HELLO remains non-admitting; BASELINE is readiness evidence; no heartbeat stream |
| Bar admission | Only READY plus HELLO; skip first partial bar | Only BASELINE_PROVEN | Only BASELINE_PROVEN; callbacks captured before proof remain discarded even if queued behind the poll lock |
| Revocation | Current/event loss, unknown/unstable source, identity/provider changes or ambiguous reconnect terminate | Any failed predicate terminates | Same terminal post-baseline rule; no reconnect recovery |

States: `PRE_BASELINE → WAIT_ALIGNMENT → BASELINE_PROVEN → STOPPED`. Any uncertainty
that violates source/identity/known-state/loss predicates may go directly to STOPPED.
WAIT_ALIGNMENT includes both waiting for an aligned event and waiting for its
independent poll; a separate latch identifies the exact event. Historical events
cannot leave a realtime alignment latch behind. No bars are buffered or anchored
before proof. HELLO is never market admission or an execution authorization.

Positive proof requires a same-object event with both current channels Connected;
known previous enums with no Disconnecting/ConnectionLost history; expected
Provider31, registered unique futures source and stable Connected current samples.
The later dispatcher poll independently revalidates both channels twice, provider,
identity, NQ DEC26 / Minute 1 / UTC / CME US Index Futures ETH configuration and
unchanged calendar hash. A BASELINE record names the aligned event sequence and
records the poll's paired UTC/QPC sample and independent source snapshots. Native
SessionIterator bounds continue to be checked per admitted bar and independently
validated against the reviewed calendar by the reader. No absent bar/session
evidence is manufactured at startup.

The 5s poll cadence is copied from Sprint 11T; passage of time proves nothing.
The 30s startup deadline, starting at REALTIME, only terminates uncertainty.
The existing overall 330s capture and 16-record bounds remain; extra callbacks can
exhaust the record budget and terminate rather than being dropped. Event loss,
unknown enum, null/foreign source, failed current validation and ambiguous reconnect
remain fail-closed. Once ready, previous non-Connected event states are terminal.

The R4 reader accepts only `arms.nt.native-timing.v3` with
`SPRINT11T_STARTUP_ALIGNMENT_R4`; old R3 evidence cannot qualify. It independently
replays event transitions, requires a later poll, checks its calendar/source fields,
deadline and QPC ordering, and rejects pre-baseline bar callback timestamps.
Windows watcher status-file I/O recovery is unchanged. No watcher is armed in R4.

Evidence supporting adaptation (historical, never reused as fresh R4 capture):

- Sprint 11T session `c02d6a4b-55b3-4592-b2fa-0332e52753df`: Connecting from
  Disconnected → WAIT_STARTUP_ALIGNMENT; Connected from Connecting → CONTINUE;
  current source Connected on both snapshots. Market HELLO follows the independent
  heartbeat (~5.010228s after first callback), not the startup callback.
- Sprint 13 market-open session `0e02836d-5355-40d2-82a6-4044b8e1db89` has the same
  two-event decisions and certified 125 FORMING / 123 CLOSED observations. The
  production exporter and its certification source hashes are unchanged.
- Sprint 11 observer `125d93a5-cf3b-43ce-bb1d-4d449e975d84` observed global and
  indicator startup callbacks. Those are separate surfaces, not a single stream
  establishing event generation or delivery latency. Duplicate startup callbacks
  are modeled explicitly; they never themselves confer baseline.
- R3 run `0d9b0949-27e3-49eb-83dd-b58855c30cde` remains the original four-record
  rejection. R4 permits waiting for **new positive evidence**, without changing
  that adjudication or inferring what would have happened after it terminated.

NinjaTrader documents distinct adapter Status and feed PriceStatus in
[OnConnectionStatusUpdate](https://ninjatrader.com/support/helpguides/nt8/onconnectionstatusupdate.htm).
That API description does not prove historical callback generation. The local
certified state machine, source audit and captured sequence justify this adaptation.

R4 validation and exact source hashes are recorded in the certification JSON under
`startup_alignment_r4`. Native compilation uses the installed
`NinjaTrader.Gui.NinjaScript.IndicatorRenderBase` (as in installed
`bin/Custom/Backup/NinjaTrader.Vendor.cs`), with no native instance created.
Compiled Cbi reachability remains the existing 17 read-only getters; no account,
order, mutation or execution call is reachable from the witness.

At offline completion, no successful R4 native capture existed. The final native
adjudication above now proves diagnostic bar timing and records the operator's
R4 replacement/recompilation. Absolute reference error, drift authority,
production-exporter emission binding and live market-analysis readiness remain
unproven. No further activation is authorized or needed for this adjudication.
No Windows setting, production exporter, runtime admission, timing tolerance,
news policy, account or connection configuration is changed. No commit or push.

Validation: the 25-module selection passed 1,205 tests; after the final queued
event/poll/bar ordering guards, all 130 focused native timing tests passed again
(overlapping counts). Reports and the exact module list are in
`.arms-dev/sprint15v/r4-regression-final.xml`, `r4-focused-final.xml` and
`r4-regression-modules.json`. This includes installed SDK compilation, the Cbi IL
allowlist, Sprint 11T readiness and whole-exporter startup, Sprint 13 native
market-open certification, Sprint 15T/15U, market data, freshness, session/calendar,
HTF and execution-risk regressions. One existing Starlette/httpx deprecation
warning remains. All 109 unrelated files, 16 datasets, 18 native evidence prefixes
and 11 saved R3 run artifacts passed preservation checks. Whitespace checks cover
all five untracked Sprint 15V files as well as the tracked diff.

The sections below retain historical R1–R3 findings and test counts, not current
R4 admission rules.

## Actual R3 capture adjudication

Only run `0d9b0949-27e3-49eb-83dd-b58855c30cde` was adjudicated as the fresh R3
capture. Native session `2fd2e707-c7fc-41c9-8a2b-7f40f2050588` has exactly four
records: HELLO, REALTIME, CONNECTION_EVENT, END, sequences 0 through 3, with no
malformed or duplicate records. Native activation occurred 140.7883882 seconds
after the reader's recorded start, inside its 600-second allowance. The immutable
receipt reproduces the saved failure exactly. The repaired watcher wrote matching
STOPPED/FAILED status and terminal records, exited, left no stderr, and now verifies
NOT_ACTIVE. This capture did not repeat the earlier watcher I/O failure.

HELLO host UTC: `2026-09-21T13:10:09.4464947Z`.
END host UTC: `2026-09-21T13:10:09.4572105Z`.
HELLO-to-END QPC duration: 0.0107087 seconds; native-start-to-END: 0.0178167
seconds; host-wall duration: 0.0107158 seconds. These are local recorded times,
not independently certified absolute UTC. File/receipt hashes are in the
certification JSON and `.arms-dev/sprint15v/r3-capture-adjudication.json`.

Connection event 0, record sequence 2, occurred in State.Realtime:

| Scalar | Actual value |
| --- | --- |
| event_status / event_price_status | Connecting / Connecting |
| previous_status / previous_price_status | Disconnected / Disconnected |
| source_status / source_price_status, before and after | Connected / Connected |
| same_source / source_valid / samples_agree | true / true / true |
| baseline_established / bar_evidence_emitted | false / false |
| continuity_before / continuity_after | PRE_BASELINE / PRE_BASELINE |

The first failed predicate is `update.Status != ConnectionStatus.Connected`,
serialized as `CONNECTION_STATUS_NOT_CONNECTED` in both the event and END.
Earlier null/identity guards passed. Other event enums are known because R3
serialized them, not because later acceptance branches were reached. No baseline
was established; zero FORMING and zero CLOSED records were emitted. This is
PRE_BASELINE_UNCERTAINTY, not POST_BASELINE_LOSS. A Disconnected-to-Connecting
startup-shaped event with already-Connected snapshots is directly supported.
Normal initialization/replayed startup is a supported interpretation, but R3 does
not record an event-generation barrier proving this notification was superseded.
Nor does it demonstrate a genuine outage. It cannot retroactively identify R2's
unrecorded enum values.

NinjaTrader documents separate current/previous connection and price statuses and
script lifecycle states; State.Realtime alone is not an event-generation barrier.
See [connection events](https://ninjatrader.com/support/helpguides/nt8/onconnectionstatusupdate.htm)
and [lifecycle states](https://ninjatrader.com/support/helpguides/nt8/onstatechange.htm).
No Connecting waiver, grace period or source-snapshot override is justified by
this capture. The witness and reader implementations remain unchanged by this
adjudication. The next evidence step is an offline review of a demonstrable
startup/event-alignment contract before proposing another native capture.

All control/connection records pass exact UTC/QPC bracket, event-time binding,
callback-before-emission and monotonic ordering checks. HELLO's NQ DEC26 Minute/1,
UTC, Provider31, CLOSE declaration and loaded calendar match the reviewed plan.
The seal matches length/count/hash, reports timer detachment and writer closure,
and an independent exclusive read-only reopen succeeds. This proves the captured
connection-callback/control provenance and cleanup only. Bar callback provenance,
native/indexed close labels, implied starts, first-tick/bar-index continuity and
actual SessionIterator bounds are NOT_OBSERVED, since no bar rows exist.

`native_timing_witness_v1.adjudicate` reproduces the native failure; its
`as_preflight_pair` adapter can bind the connection-event pair but supplies no
reference or drift bounds. `clock_preflight_v1.assess` returns UNKNOWN with
REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING and every operation disabled. The reviewed
`clock_evidence_v1.collect` likewise passes no ReviewedBounds; public measurements
are not absolute authority and no new probe was performed for this adjudication.
EXPORTER_EMISSION_BINDING_MISSING remains open for production market-exporter
rows; even successful witness-owned control pairing cannot supply that binding.
Remaining blockers are a proven startup baseline, at least three complete CLOSED
observations, exact market-exporter emission binding, reviewed absolute-reference
and drift/capture-error bounds, same-epoch mapping and operation-specific windows.
No market-analysis, PAPER, SIM or LIVE readiness is granted, and no watcher is rearmed.

Adjudication regressions passed 1,171 tests across the existing 24-module selection,
including all 100 Sprint 15V tests, installed-SDK compilation/read-only IL audit,
Windows I/O stress and the synthetic replay of this exact observed event shape.
The replay checks all event scalars, PRE_BASELINE retention, zero bar emissions,
the exact terminal reason and UNKNOWN preflight authority. Synthetic replay is
not fresh native evidence. Results are in `r3-adjudication-regression.xml` under
`.arms-dev/sprint15v`; one existing Starlette/httpx warning remains. Diff checks
include all new files. The three changed repository files are the Sprint 15V
test module, certification JSON and this document; witness and reader code did
not change. All R3 artifacts, 109 unrelated files, 16 datasets and 18 prior native
evidence prefixes were hash-checked for preservation. No commit or push was made.

## R3 Windows status I/O recovery

Run `44ca9da9-c5c4-4101-a787-b19490481ae9` failed before native activation.
The retained traceback identifies `Path.replace` / `os.replace`, from
`status.json.tmp` to `status.json`, with `PermissionError`, Windows error 5.
The exception handler wrote WATCHER_IO_FAILED, then the final STOPPED projection
failed at the same replacement operation. The persisted ACTIVE status was stale;
the inbox was empty and PID 87884 had exited. Original artifacts are preserved.

A controlled local reproduction holds a reader handle and demonstrates the same
WinError 5. On this workstation `os.replace` fails even with read/write/delete
sharing; `ReplaceFileW` succeeds with those flags and fails with error 32 without
delete sharing. Removing the controlled reader allows replacement again. This
establishes a Windows reader/replacement compatibility defect. It does not identify
the original handle owner after the fact: the verification process read status
concurrently, but its handle details were not captured. There is no evidence of
another watcher, browser, dashboard, antivirus, indexer, or stale owner causing
this incident. Repeated successful writes and current write tests do not indicate
a persistent directory ACL denial; no ACL or Windows configuration is changed.

The Python diagnostic writer now uses a unique exclusive temporary file in the
same directory, writes complete JSON, flushes/fsyncs and closes it, then publishes
with ReplaceFileW for an existing destination. Initial publication uses rename.
Known Windows lock errors have at most 20 retries at 25 ms; unexpected errors
fail immediately. Only the invocation's own temporary file is cleaned, with a
bounded cleanup retry. A permanently held foreign handle can prevent deletion;
that is an error, not permission to delete unrelated files or keep waiting forever.
Readers use CreateFileW with FILE_SHARE_READ|WRITE|DELETE and bounded open retries
for brief replacement/name-transition conflicts, never cached ACTIVE fallback.
The 2,000-write stress test checks complete JSON and nondecreasing sequences with
three concurrent readers. Expected injected lock errors are distinguished from
unhandled sharing failures.

An exclusive permanent run claim still prevents reuse and duplicate writers.
Status identifies run UUID, watcher UUID, PID and process creation FILETIME, plus
a monotonic heartbeat sequence/time and two-second lease. `verified_status` requires
matching claim identity, a live matching process creation time, multiple advancing
heartbeats and fresh age. Access denial, missing/malformed data, a frozen heartbeat,
PID reuse, terminal/result presence or process exit returns NOT_ACTIVE. This is a
point-in-time observation, not permanent authority after verification. Old status
files are never upgraded merely because they say ACTIVE_AND_WAITING.

Orderly exit writes a separate flushed terminal.json with FAILED or COMPLETED
before attempting the STOPPED status projection. If status stays locked, the
terminal file still vetoes stale ACTIVE. Abrupt process death may leave an old
ACTIVE file but is rejected independently by the process check. Filesystem loss
can prevent terminal persistence; absence of live evidence still fails closed.
No guarantee of power-loss durability beyond the filesystem is claimed.

Use `py -B -m tools.native_timing_witness_v1 status --run-directory <run>` to verify
waiting. Do not use a Get-Content snapshot as a liveness verdict. The `dry-run`
subcommand is a five-second NON_NATIVE_DRY_RUN status lifecycle with no native
inbox access. Independent dry-run evidence is retained under
`.arms-dev/sprint15v/io-recovery/be5783eb-409b-4226-ac0c-9a9e83d61ea6`:
STARTING, ACTIVE_AND_WAITING, four verified heartbeat samples, COMPLETED/STOPPED,
then NOT_ACTIVE with zero surviving dry-run processes. It also rejects the failed
run's old ACTIVE projection. No native source or compiled witness changed in this
recovery; operator recompilation is unnecessary for this Python-only fix.

Recovery validation passed 1,169 tests across the existing 24-module selection,
then 99 final focused tests after adding explicit rejection of missing process
identity (overlapping counts). Each completed focused stress run performs 2,000
writes with three concurrent readers; no unhandled sharing failures or partial
JSON occurred in the passing runs. Deliberate incompatible locks reproduce errors
5/32 and exercise bounded retry/failure. The existing Starlette/httpx warning remains.
Reports: `.arms-dev/sprint15v/r3-io-focused.xml` and `r3-io-regression.xml`.

Platform behavior: [CreateFile sharing](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea),
[ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew),
[process creation times](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).

## Sprint 15V-R3: exact connection event diagnostic

R2's exact enum cannot be reconstructed. The sealed R2 record proves
`CONNECTION_STATUS_NOT_CONNECTED` and the predicate
`update.Status != ConnectionStatus.Connected`; its earlier null/identity checks
passed. PriceStatus and both previous enums were not serialized and remain
UNKNOWN. Observer and Sprint 11T/13 evidence is older. The available September 21
NinjaTrader log/trace files contain no connection entries around 12:29 UTC
(08:29 local). Historical Connecting notifications with Connected snapshots
corroborate a startup hypothesis but cannot identify or supersede the R2 callback.
The R2 watcher had also expired before activation; its evidence is not reclassified
as a successfully admitted capture.

R3 emits `arms.nt.native-timing.v2` with HELLO contract
`STRICT_EVENT_BASELINE_R3`. Each connection callback after source selection emits
a bounded CONNECTION_EVENT record with the four copied event enums, event sequence,
callback-entry UTC/QPC bracket, lifecycle state, whether bars were already emitted,
and continuity state before/after. Current pinned-source status/price snapshots on
both sides of source validation expose disagreement without inferring atomicity.
Unknown enum integers are preserved as `UNDEFINED_<integer>`; unavailable event
values are `UNAVAILABLE`. No connection names, credentials or account data appear.
Null and unrelated events still terminate and are reported explicitly.

The diagnostic starts PRE_BASELINE. Its only baseline transition requires a fresh
same-source callback in Realtime, all four current/previous event enums Connected,
valid unchanged source identity and agreeing Connected status/price snapshots.
A healthy event before Realtime does not establish the baseline. Pre-baseline bar
callbacks emit nothing and do not anchor later observations. The reader independently
replays this contract and rejects any bar before BASELINE_PROVEN. This is a strict
local diagnostic contract, not proof of transport continuity or absolute UTC.

The seven existing failure predicates retain their first-failure order. Connecting,
ConnectionLost, Disconnected and non-Connected previous statuses are never waived.
A pre-baseline failure stays PRE_BASELINE and terminates; a failure after baseline
changes state to CONTINUITY_LOST and terminates. Reconnection cannot resume the run.
If the original predicates pass but current source validation fails, the additional
reason is CONNECTION_SOURCE_SNAPSHOT_UNPROVEN. Healthy duplicate events are recorded
with distinct event sequences. A quiet source without a qualifying callback may
reach WINDOW_END without bars; no sleep, grace period or synthetic baseline is used.
The 16-record limit remains enforced, including connection events. Event floods
can therefore terminate with RECORD_LIMIT before three CLOSED observations.

NinjaTrader documents separate connection and price-feed statuses and current/previous
event fields, but does not supply a generation barrier in this callback contract:
[OnConnectionStatusUpdate](https://ninjatrader.com/support/helpguides/nt8/onconnectionstatusupdate.htm),
[ConnectionStatusEventArgs](https://ninjatrader.com/support/helpguides/nt8/connectionstatuseventargs.htm).
R3 does not assume a Connecting event is stale merely because a snapshot is Connected.

Repeat procedure: the operator must replace/recompile the NinjaTrader copy from
the current repository source and confirm readiness before a watcher is launched.
Do not activate the indicator yet. After readiness, prepare exactly one new run
with an empty isolated inbox and start its reader; independently verify the live
PID, advancing heartbeat, waiting flag and empty inbox. The activation allowance
is 600 seconds from watcher start, followed by the unchanged 330-second native
capture and 15-second seal-delivery budget. Return the new UUID, directory and
deadline, then stop for operator activation on the separate NQ DEC26 Minute/1,
UTC, CME US Index Futures ETH diagnostic chart. Never reuse R2 paths or evidence.
The v2 schema and HELLO contract reject an old compiled witness.

No R3 capture or absolute clock authority is claimed by offline tests. Reference
and drift bounds remain unresolved. Runtime admission, exporter, Windows settings,
timestamp policy, PAPER and news policy are unchanged. The supporting reader,
tests and certification change only to validate this diagnostic stream.

R3 validation: 84 focused tests passed, including installed-SDK compilation and
the 17-getter Cbi audit; 1,155 tests passed across the 24-module regression selection
(counts overlap). This includes Sprint 15T/15U/15V, connection observer, Sprint
11T/13, market data, freshness, sessions, aggregation and execution-risk gates.
The only warning is the existing Starlette/httpx deprecation. Exact commands and
results are in `.arms-dev/sprint15v/r3-focused.xml`, `r3-regression.xml`, using
the unchanged `r2-adjudication-regression-modules.json` selection and the reviewed
Sprint 15R test-environment profile. No live capture was run by these tests.

`ArmsNativeTimingWitnessV1` is a separate, bounded market-metadata indicator.
It owns its diagnostic JSONL session and observations. The companion Python
watcher adjudicates those observations without constructing a candle authority,
market reader, paper engine, account service, or dashboard ingestion runtime.
The existing `ArmsReadOnlyMarketV1` source and behavior are unchanged.

## Exact binding and its limit

At entry to OnBarUpdate the witness captures QPC, DateTime.UtcNow, QPC in that
order, before locks, metadata reads or I/O. The middle DateTime value is saved
once, with its full 100 ns .NET ticks and round-trip UTC text. QPC brackets expose
preemption or read overhead rather than assuming simultaneity or zero error.
Each emitted record then captures another identical three-read sequence after
copying the observation metadata. That second pair supplies the record's exact
`event_time`; there is no second independent wall-clock read for that field.

The emission sequence is:

1. Capture the callback-entry pair.
2. Require primary-series first-tick Realtime and unbroken bar continuity.
3. Check the pinned Provider31 connection and instrument/period/application zone.
4. Recheck loaded calendar metadata, then copy source/indexed label and native
   session metadata inside this callback.
5. Capture the emission pair, serialize its same UTC value as event_time and
   write/flush the record.

CLOSED and FORMING emitted by the same callback carry an identical callback pair
and callback bar index. Each has its own sequence and emission pair. Consequently
there is no sibling-indicator or equal-label guess about the diagnostic emission.

This resolves exact emission binding **for the witness-owned stream**. It does
not claim that this indicator shares callbacks with another chart, retrospectively
pair old ArmsReadOnlyMarketV1 rows, or turn the witness into a certified live-data
replacement. Any later transfer of these findings to the production path requires
an explicit integration review. Native capture and formal UTC eligibility remain
separate outcomes.

## Fields and checks

HELLO pins a fresh capture-run UUID supplied by the reader and a new native session
UUID generated by the indicator. It records Provider31/NQ DEC26/Minute 1/UTC/CME
US Index Futures ETH, CLOSE semantics, QPC frequency, native start QPC, loaded
calendar JSON and its SHA256. No account/provider-owned private strings are emitted.
Sequences start at zero and cover HELLO, REALTIME, CONNECTION_EVENT, observations and END.

Each observation includes raw Time[ago] and Kind, Bars.GetTime(index) and Kind,
current callback bar index, observed bar index, bars-ago, first-tick flag, state,
period, instrument and trading-hours identity. A checked UTC application permits
mapping Utc/Unspecified wall labels into UTC; Local Kind is rejected. Raw values
are preserved. For a reviewed full one-minute bar the implied start is its native
close minus exactly one minute; it is never inferred from receipt time.

SessionIterator supplies actual native begin/end/trading day. The reader compares
these with the reviewed loaded ordinary calendar snapshot and rejects unsupported
holiday/partial dates, changed calendars, session transitions and clipped minutes.
The indicator recomputes its loaded semantic calendar snapshot on each captured
callback; this is not a claim that NinjaTrader exposes the XML's byte hash.

The first observed realtime bar after baseline is anchored and excluded from CLOSED capture,
matching the existing exporter's conservative first-bar behavior. Duplicate,
backward or missing callback indices/labels terminate capture; bars are never
manufactured. Historical callbacks do not emit market observations. Realtime
reentry, restart and connection continuity loss cannot silently resume a run.

## Bounded lifecycle and writer closure

Capture starts at DataLoaded and stops automatically after at most 330 scheduled
seconds, or sooner after three consecutive complete CLOSED observations. The
budget covers roughly 30 seconds startup, up to one minute alignment and four
minute transitions. In the normal complete trace there are five FORMING, three
CLOSED, HELLO, REALTIME, one healthy CONNECTION_EVENT and END: 12 records,
below the hard maximum of 16. Additional connection events consume that same budget.
No ticks or delayed startup can produce an INCONCLUSIVE deadline result; this
budget is not permission to invent a missing observation or loosen freshness.

A thread-pool deadline timer and callback checks enforce the monotonic budget.
Timer scheduling and local file I/O are not hard-real-time guarantees. The reader
rejects observations outside the native window and expires its own bounded wait.
No historical calculation or market-hours delay can leave a reader armed forever.

Termination writes END, detaches the timer, releases the read-only connection
reference, disposes the writer, and only then writes a separate exclusive seal
containing complete-file length/SHA256/record count. The seal is disposed before
an atomic rename publishes it; temporary and late seals cannot complete a capture.
A missing or inconsistent
seal fails closed. Synthetic execution checks that the writer/timer/source fields
are released and the file can be reopened exclusively after terminal cases.

## Read-only boundary

The installed SDK compile uses the existing offline IndicatorBase shim for the
editor-generated Indicator class. Real SDK assemblies are inspected as metadata;
the diagnostic is not instantiated outside NinjaTrader. The compiled Cbi calls
are exactly 17 allowlisted getters on Instrument/MasterInstrument, Connection,
ConnectOptions and ConnectionStatusEventArgs. There are no Account/Order types,
trading calls, mutation calls, dynamic invocation or reflection in the witness.
The safety statement applies to the diagnostic's own reachable code, not a claim
that the running NinjaTrader application has no unrelated account functionality.

The executable unit-test harness compiles the actual witness source against
synthetic SDK types, never the real runtime. It drives callback/state transitions,
including an actual deadline timer firing. No account discovery, broker API,
PAPER entry or connection mutation occurs in production/native testing.

## Clock Preflight / Clock Evidence binding

`as_preflight_pair` retains both run/session identities and converts raw QPC
brackets outward to integer microseconds. UTC conversion includes a declared
one-microsecond quantization component, not a guessed total capture-error bound.
The bracket width remains available for a separately reviewed capture-error budget.
The reader records its own QPC/UTC brackets before activation and around final
file receipt; it requires native QPC observations to fall inside those bounds.

Combining a native pair with Clock Evidence V1 requires an explicit same-host,
same-boot QPC/epoch mapping, reviewed reference-error/drift bounds valid throughout
the interval, sample-age propagation, and a per-record operation window. Different
capture UUIDs are not silently relabeled as one epoch. Host UTC alone is not true
UTC. Provenance PASS does not certify candle freshness, future-data eligibility,
or absolute UTC accuracy; all clock readiness remains UNKNOWN here. The final
file read is capture receipt, not a fabricated per-tick ingestion receipt.

Missing reference/drift authority does not block this bounded diagnostic capture.
It continues to block live market admission and all entry authority. No new NTP
investigation or Windows change is part of Sprint 15V.

## Watcher and operator boundary

The watcher uses one exclusive claim and a fresh empty private inbox. It rejects
old evidence, multiple native sessions and reuse of a completed run. It reports
ACTIVE_AND_WAITING only after the claim, empty-inbox check and reader QPC anchor.
Independent process liveness and increasing status heartbeat must be checked;
a status file alone is insufficient. Activation expires after 600 monotonic
seconds; native completion has its separate 330-second budget and 15-second
file-seal delivery budget. These are diagnostic deadlines, not timestamp tolerance.

Only after offline checks pass and the reader is independently waiting may the
operator copy this new indicator source into their NinjaScript Indicators folder,
compile in the editor and apply it on a **separate** NQ DEC26 one-minute chart
using the existing Provider31 source, UTC application zone and named ETH template.
Set only the provided fresh private timing directory and capture-run UUID.
Leave ArmsReadOnlyMarketV1 and its existing chart unchanged. Do not add the SIM101
witness. The timing witness ends automatically and makes no market-data admission.
If the activation deadline expires, obtain a fresh reader before activation.

Do not deploy the private offline compilation DLL; NinjaScript Editor compiles
the supplied source through its own generated Indicator class. A local SDK compile
is not a claim that editor import/activation has already occurred.

## Validation and scope

### Sprint 15V-R2 native reason-code adjudication

Run `2de1258b-7862-42d9-add3-724cbe18b359` contains native session
`6dbc00c4-7606-4b69-a6ff-7bd50a954fdc`. Its three records are HELLO, REALTIME,
END, sequences 0-2. END line 3/sequence 2 says exactly
`CONNECTION_STATUS_NOT_CONNECTED`: `update.Status != ConnectionStatus.Connected`.
Earlier guards therefore passed: the event and connection were non-null, and
the event connection was the pinned object. An unrelated connection/identity
mismatch did not trigger this termination. Price/previous predicates were not
reached; their values cannot be inferred. The actual Status enum was not stored,
so Connecting, Disconnected, ConnectionLost or another non-Connected value cannot
be distinguished. This identifies R2's branch, not the original run's lost event.

Two independent failures must remain separate. The watcher stopped with
`ACTIVATION_TIMEOUT` at its original 600-second allowance. Native start QPC was
40.9988859 seconds beyond the published monotonic activation deadline. There is
no watcher receipt and none was reconstructed. The late sealed file is useful
for terminal branch diagnosis only; it is not a watcher-admitted timing capture.
The original watcher result/status and native file/seal are retained unchanged.

Host timestamps are 2026-09-21T12:29:00.4877933Z through
2026-09-21T12:29:00.4915441Z. HELLO-to-END QPC is 0.0040627 seconds;
native startup-to-END is 0.0153198 seconds. Host wall duration is 0.0037508 seconds.
These do not certify absolute UTC. Schema, contiguous sequence, monotonic control
pair ordering, loaded calendar, identity, length/hash-bound seal and exclusive
writer reopen pass. There are zero malformed/duplicate records and zero
FORMING/CLOSED observations. The required three closed observations are absent.

NinjaTrader's Status represents the adapter channel; PriceStatus is separate.
The historical observer/11T/13 startup trace demonstrates that Connecting events
can be delivered while source snapshots are Connected, making the witness's
snapshot-only startup assumption a plausible explanation. That corroboration
does not establish this event's enum, a real loss, or a harmless startup replay.
No continuity exception or startup correction is objectively justified from this
reason code alone. The native witness and reader remain unchanged by this
adjudication; no repeat capture is requested and no watcher is armed.

Control UTC/QPC pairing does not bind missing bar callbacks. Clock Evidence still
supplies no reviewed reference/drift authority, and Clock Preflight remains
UNKNOWN for market analysis. The next evidence requirement is to distinguish
the same-source event's actual Status and contemporaneous current-source snapshot
using existing scalar diagnostics if available. Any later diagnostic improvement
must preserve the guard. Do not infer a value or deploy the proposed startup
contract to make this failed capture pass.

R2 adjudication validation passed 1,130 tests across the 24-module connection,
clock, native timing, market, session, freshness, HTF and safety selection,
including 59 Sprint 15V tests and installed-SDK compile/API audit. New coverage
rejects even sealed evidence first seen after activation expiry and confirms that
files arriving after timeout do not replace the failure or fabricate a receipt.
Exact selection/results: `.arms-dev/sprint15v/r2-adjudication-regression-modules.json`
and `r2-adjudication-regression.xml`. A private module-list serialization issue
was corrected before the successful test invocation; it did not change code or
native evidence. One existing Starlette/httpx deprecation warning remains.

### Sprint 15V-R1: exact continuity guard diagnosis

The exact native branch remains unknown. The failed record did not preserve event
arguments, and no inspected sidecar covers 2026-09-21 11:56:05 UTC. The prior
Sprint 13 market session ended at 04:02:15 UTC, so its heartbeats cannot establish
continuity around this failure. The original evidence and original source hash
remain bound in the artifact; new reason codes do not relabel that evidence.

There is one call site for the old ambiguous stop reason. Its six OR predicates
are enumerated below, with the identity predicate split into null and unequal
objects. R1 changes only the fixed reason emitted by its first failing predicate,
in the original short-circuit order. No status, identity, or previous-status
condition is waived. No new provider getters or subscriptions were introduced.

| Original predicate | R1 fixed reason |
| --- | --- |
| `update == null` | `CONNECTION_EVENT_NULL` |
| `update.Connection == null` (identity clause) | `CONNECTION_EVENT_SOURCE_NULL` |
| Non-null `update.Connection` is not pinned `source` | `CONNECTION_IDENTITY_MISMATCH` |
| `update.Status != Connected` | `CONNECTION_STATUS_NOT_CONNECTED` |
| `update.PriceStatus != Connected` | `CONNECTION_PRICE_NOT_CONNECTED` |
| `update.PreviousStatus != Connected` | `CONNECTION_PREVIOUS_STATUS_NOT_CONNECTED` |
| `update.PreviousPriceStatus != Connected` | `CONNECTION_PREVIOUS_PRICE_NOT_CONNECTED` |

Identity mismatch does not assert replacement: it can also be an unrelated
connection notification. The first failed predicate is exact, but is not a claim
that all later predicates passed. Null/uninitialized event data is ambiguous;
the public documentation does not promise it is a normal startup notification.
Healthy Connected-to-Connected duplicates pass. A price/provider transition or
non-Connected previous state remains terminal even if the current source is
Connected. Reconnect never revives a terminated witness.

The witness does not explicitly subscribe: it overrides the host-dispatched
OnConnectionStatusUpdate method. The application cannot infer the host's internal
subscription time from that override. DataLoaded sets `started`, validates and
pins a source snapshot in SafeSource, then opens the writer and emits HELLO under
the same lock. The callback returns while not started, stopped, or source-null.
An unavailable initial source instead fails startup without opening evidence.
Realtime only sets the lifecycle flag and emits a control record; it does not
establish an event-aligned connection baseline. The first bar requires Realtime
and another successful source/calendar check. Pre-baseline events are not retained
as evidence; a passing snapshot is not proof of earlier continuity. The lock
serializes local handling, not provider event creation or queue order.

The historical 11S observer (`125d93a5-cf3b-43ce-bb1d-4d449e975d84`) recorded a
Disconnected-to-Connecting, then Connecting-to-Connected pair during DataLoaded
on the GLOBAL channel, repeated during Realtime on the INDICATOR channel. All
44 current-source samples were Connected. The 11T sidecar and Sprint 13 startup
sidecar also observed this transition pattern. Thus transition/previous-state
predicates can occur during an apparently healthy startup; this supports an
ordering explanation but proves neither event supersession nor the failed
15V callback's arguments. It is not proof of continuous connectivity at 11:56.

NinjaTrader documents status/price channels and their previous values separately,
and defines Realtime as the start of realtime processing. It does not give an
event-generation barrier that would classify all preceding callbacks as stale.
See [ConnectionStatusEventArgs](https://ninjatrader-live.ninjatrader.com/support/helpguides/nt8/connectionstatuseventargs.htm),
[OnConnectionStatusUpdate](https://ninjatrader.com/support/helpguides/nt8/onconnectionstatusupdate.htm),
and [State](https://ninjatrader.com/support/helpGuides/nt8/state.htm).

**Startup design only, not implemented:** if event alignment is introduced after
review, use PENDING -> ALIGNED -> OBSERVING -> TERMINAL states. Pin and validate
the source before ALIGNED; admit no bars while pending. An observed actual loss,
unknown/null/foreign identity or changed current snapshot terminates. A known
initial Connecting transition can remain pending, without declaring it stale;
require an aligned same-source Connected callback and a subsequent independent
healthy snapshot on a later realtime bar callback before entering OBSERVING.
Anchor a new first bar there, exclude the partial bar, and never replay pending
bars. After OBSERVING, previous non-Connected state is terminal. An ambiguous
queued event is never ignored. The existing monotonic capture deadline bounds
pending initialization; no sleep or arbitrary grace delay is needed. This
design permits fail-closed unavailability and does not guarantee startup success.
The existing Sprint 11T runtime remains unchanged; its contract is corroborating
architecture, not automatically imported authority for this diagnostic.

R1 has not established that this failed callback was a normal initialization
event, so no startup policy exception is implemented. Per the user's repeat gate,
no new watcher is prepared or armed. The diagnostic improvement is offline only;
another native diagnostic activation would need an explicitly revised capture
gate while exact attribution remains unavailable from retained evidence.

R1 validation: 58 focused tests and 1,129 tests across 24 regression modules
passed (overlapping counts). The focused suite compiles against the installed
SDK and confirms the same 17 Cbi getters, with no Account/Order/mutation calls.
Every new reason branch, precedence of combined startup conditions, pre-baseline
and pre-Realtime events, initial missing/disconnected snapshots, duplicate healthy
callbacks, disconnect/reconnect terminality, and initial FORMING/CLOSED behavior
are covered using synthetic SDK execution. No synthetic record is native proof.
Exact commands/modules and results are retained in private
`r1-regression-modules.json`, `r1-focused.xml` and `r1-regression.xml` under
`.arms-dev/sprint15v`. The existing Starlette/httpx warning remains.

### Native run adjudication: 1b56facc-384b-436b-9098-27efdee164fa

The requested fresh run failed. Native session
`38c5bbd5-762e-416c-bfdf-b10977266e9f` contains exactly HELLO, REALTIME and END,
with sequences 0, 1, 2; no malformed or duplicate records. HELLO is the startup
record (the schema has no literal START kind). The first failure witness is line
3, sequence 2: `CONNECTION_CONTINUITY_UNPROVEN`, with zero CLOSED records.
There are also zero FORMING records. Waiting longer could not add observations
after this automatic termination; this is a continuity failure, not an otherwise
valid capture that merely ran out of time.

HELLO host UTC is `2026-09-21T11:56:05.4624975Z`; END host UTC is
`2026-09-21T11:56:05.4737493Z`. HELLO-to-END QPC duration is 0.0111244 seconds;
native start-to-END is 0.0305763 seconds. Wall duration is 0.0112518 seconds.
These are recorded host times, not certified absolute UTC. All three control
records have internally valid UTC/QPC brackets, callback-before-emission ordering
and monotonic progression. This does not establish OnBarUpdate provenance,
bar-label/implied-start semantics or native session boundaries: no bar observation
was emitted. HELLO identity and its loaded calendar match the reviewed plan.

Independent adjudication using the immutable reader receipt exactly reproduces
the watcher failure. The completion seal matches file length, count and SHA256;
an exclusive read-only reopen independently confirms the writer is closed. The
watcher is STOPPED and no replacement is armed. Raw evidence, seal, receipt and
original watcher result are retained in the private run directory; only their
privacy-safe summary and hashes enter the certification artifact.

The verified cause of termination is the conservative connection callback guard.
Its single reason covers null event arguments, a different connection object,
non-Connected current status, or non-Connected previous status. Event arguments
were not recorded, so the evidence does **not** prove an actual Provider31 outage
or distinguish a startup notification from connection loss. Synthetic regressions
exercise alternative pre-bar notifications and verify the same three-record
failure shape, closure and zero granted authority; these are not native evidence.

The shortest next step is a read-only review of existing connection diagnostics
at the capture time. If those cannot identify the trigger, review a narrowly scoped
privacy-safe scalar reason diagnostic in the timing witness before another capture;
do not remove the guard or repeat the unchanged capture blindly. No witness source,
connection, Windows setting, exporter or runtime admission policy was changed by
this adjudication.

`native_timing_witness_v1.as_preflight_pair` can convert the control-record pairs,
but supplies neither reference nor drift bounds. `clock_evidence_v1` measurements
do not create `ReviewedBounds`; old measurements are not fresh evidence for this
run. Calling `clock_preflight_v1.assess` without reviewed bounds still returns
UNKNOWN with `REVIEWED_ERROR_AND_DRIFT_BOUNDS_MISSING` and every operation blocked.
Even after a successful future native provenance capture, absolute reference
error, drift/capture-error validity, same-clock epoch mapping and per-record
operation windows must be established separately. This run resolves startup
identity, control-record pairing and cleanup only; paired market timing remains
NOT_PROVEN. MARKET_ANALYSIS, PAPER, SIM and LIVE readiness are not granted.

Adjudication validation passed 991 tests across 17 modules, including all 48
Sprint 15V tests and installed-SDK compilation/IL inspection. The exact selection
is retained in `.arms-dev/sprint15v/adjudication-regression-modules.json` and JUnit
results in `.arms-dev/sprint15v/adjudication-regression.xml`. It covers Sprint
15T/15U/15V, native timestamps and certification, NinjaTrader market data, loaded
calendars, session lifecycle, closed-bar HTF aggregation, quote/signal freshness,
market data hub/provider, market hours and execution risk gates. One existing
Starlette/httpx deprecation warning remains. Source/runtime policy is unchanged.

Tests execute the actual C# witness logic for FORMING/CLOSED, same-callback pairing,
sequence/minute progression, Historical to Realtime, restart, duplicate/out-of-order
callbacks, missing boundaries, calendar/zone changes, connection loss, timer expiry
and writer closure. Reader mutation tests cover malformed JSON/extra fields,
truncation, epoch/frequency/receipt mismatch, bad seals and immutable timestamp
binding. Watcher tests prove waiting precedes fresh input and all exits are bounded.
The installed SDK compilation and compiled Cbi call allowlist are regression tests.

The 59-module relevant regression selection passed 1,959 tests, including the
initial 41 new tests. After the final atomic-seal and deadline checks, the focused
native timing suite passed all 43 tests (overlapping count). Recovery confirmed
both complete reports, parsed the recovered files, and verified preservation
hashes before editing the documentation. The selection is the existing 55-module Sprint 15T list plus Sprint 15U,
Sprint 15V and the two existing private Sprint 15S analysis/news suites. It covers
Sprint 13 native timestamps/calendars, 15T/15U, market/freshness/session/HTF,
operational PAPER, dashboard/API, news and execution safety. The existing reviewed
test_environment profile and hash-checked private dataset map were used; no runtime
profile changed. One existing Starlette/httpx deprecation warning remains.
Whitespace checks include the five new files. Unrelated 109 files, 16 datasets
and 18 native evidence prefixes are hash-checked for preservation.

Proposed files: the new indicator, `tools/native_timing_witness_v1.py`,
`backend/tests/test_native_timing_sprint15v.py`,
`backend/tests/native_timing_sprint15v.json`, and this document.
No prior source or tolerance file is modified. Native deployment is an operator
step. No commit is authorized by the consumed Sprint 15U commit permission;
no staging, commit or push is performed in Sprint 15V.

Platform references: [Microsoft QPC](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps),
[NinjaTrader bar labels](https://ninjatrader.com/support/helpguides/nt8/how_bars_are_built.htm),
[Calculate](https://ninjatrader.com/support/helpguides/nt8/calculate.htm), and
[GetTime](https://ninjatrader.com/support/helpguides/nt8/gettime.htm).
Installed SDK compilation and the prior native calendar/market certificates,
not these documents alone, bind this workstation's API and configuration checks.
