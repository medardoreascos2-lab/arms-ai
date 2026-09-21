# Sprint 15Y — fresh same-host native stream adapter

Baseline: `d9daa6f086a3985e5aba8a1fb6bb756ca2e3c018`, branch
`refactor/backend-architecture`. ANALYSIS ONLY. No native activation, new capture,
account access, commit or push was performed by this sprint.

## What changed and why

Sprint 15X provided an isolated analysis object and dashboard contract but no file
delivery or startup cursor. Its sequence-zero admission could not attach to an
already-running exporter without replaying history. `FreshNativeAdapterV1` now
tails the canonical file and production sidecar, validates their correspondence,
and supplies newly observed rows to that same profile. It never routes through
`CurrentPaperServiceV1`, the account-backed application or an execution service.

The production C# source, canonical schema and existing absolute-time admission
gates are unchanged. The installed exporter source must match the normalized
Sprint 15W fingerprint. The existing compiled Sprint 15W exporter can be used;
another NinjaTrader compile is not required if that installed version is retained.
The source hash verifies the file, not a compiled assembly: the operator's prior
successful compilation remains the deployment prerequisite.

## State and cursor contract

| State | Meaning | Analysis |
|---|---|---|
| WAITING | Reader/backend started; no canonical session discovered | Unavailable |
| BOOTSTRAP | One session bound; pre-cursor records validated/discarded; waiting for a new forming boundary | Unavailable |
| LIVE_TAIL | A new paired FORMING boundary passed the QPC fence; subsequent rows pass the profile | Source-relative, after warmup |
| DISCONNECTED | Exporter terminal/seal or explicit adapter shutdown | Revoked; no recovery |
| REVOKED | Integrity, timing, IO, epoch or lifecycle failure | Revoked; no recovery |

At discovery the canonical file's byte length is the startup cursor. A line that
began before this cursor is historical even if its final bytes arrive later.
The adapter also fixes a reader-start QPC fence when constructed. A boundary whose
callback predates that fence remains bootstrap, even if appended later. Bootstrap
rows establish metadata and exact sequence/pair cursors; they never enter candle
history or produce LIVE observations. Hashes, callback ordering, identity and
canonical/pair sequence remain checked across the discarded prefix.

At the first newly appended, post-fence FORMING record, a one-time profile baseline
binds the validated HELLO metadata and preceding sequence cursors. No historical
receipt or emission is invented. On late attachment, the first observed bar is
partial: its later CLOSED is checked but not analyzed. A whole subsequent bar
must be observed before any close is released. A CLOSED/FORMING pair must share
the same callback; analysis stays unavailable while the pair is incomplete.

On adapter restart there is a new process-local epoch and startup cursor, and no
restored live authority or analysis history. A new exporter UUID/file/sidecar
revokes the existing adapter rather than merging sessions. A new adapter baseline
is required. Use a new isolated directory for a new exporter activation; a
directory containing multiple canonical sessions is rejected.

## Same-host transport and integrity

The launcher uses Windows QueryPerformanceCounter through the existing native
timing helper, matching the C# Stopwatch counter family. Every sample checks
epoch, frequency and monotonic progression. File access is restricted to absolute
paths on local fixed drives, with UNC and reparse/symlink ancestry rejected.
NinjaTrader remains under operator control. No process/account discovery occurs.

Read handles request only GENERIC_READ and share read/write/delete, so they work
with the exporter's FileShare.Read writer and can detect later replacement.
This follows the Windows [CreateFileW sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew);
ownership of the handle transfers through Python's
[msvcrt.open_osfhandle](https://docs.python.org/3/library/msvcrt.html#msvcrt.open_osfhandle).
Tests exercise these sharing settings against a temporary native Windows handle.

Each file is pinned by device/file identity. Each poll checks path identity, size
and SHA256 of the already-consumed prefix using unbuffered reads. Truncation,
same-inode overwrite, replacement, missing files, directory replacement, malformed
rows and changed UUIDs revoke the tail. Raw canonical JSON bytes, excluding their
line ending, must hash exactly to the sidecar's canonical_sha256. The session,
canonical sequence, pair sequence, kind, close label, source identity and QPC
frequency/order must agree. Every live bar then passes the Sprint 15X profile's
OHLCV, source-label/index continuity and callback-provenance checks as well.

Writer identity here means the pinned file/session under the reviewed exporter's
CreateNew lifecycle. It is not cryptographic process attestation. The trust
boundary is the operator-controlled local output directory and installed exporter;
hostile local processes able to forge files/QPC evidence are outside this protocol.
No assertion of operating-system writer PID ownership is made.

Bounds are explicit local observation policy, not absolute timestamp tolerances:
15 nominal QPC seconds without an accepted receipt, 90 without paired emission,
5 for a missing pair/partial line/orphan pair, and 900 for operator activation or
bootstrap. Overrides may tighten but cannot widen these limits. The 90-second
observation cutoff permits ordinary one-minute callbacks with a 30-second local
grace; it does not certify exchange latency or alter the existing 30-second
absolute-time market-admission policy. Quiet/stalled streams revoke rather than
remaining LIVE on heartbeats alone. Drift-qualified SI elapsed bounds remain
unproven, so these are labeled nominal QPC observations.

Reads are capped at 64 KiB per poll, 16 KiB per line, 1,024 pending rows per channel,
and 32 MiB per file. Oversize/backlogged input revokes; no silent eviction or
automatic rotation. Prefix verification has bounded linear cost in retained file
size. A new baseline is required at a resource limit. Partial records do not count
as heartbeat activity. Pending pairs suppress all component values immediately;
timeout then latches revocation. Completed seal/temporary seal or canonical
DISCONNECTED revokes immediately; the adapter never fabricates a seal or claims
the open stream is an archived, complete capture.

## API, dashboard and authority

`create_market_analysis_time_app_v1(adapter=...)` starts a 250 ms polling task
only when the explicitly created app enters lifespan. Unexpected worker failure
revokes the adapter; shutdown closes all reader handles. GET also polls under the
same lock, making worker stalls observable. There is no ingestion, reset, recovery,
execution or account route. The launcher binds one worker to 127.0.0.1 only.
Importing the launcher or running `--help` starts nothing.

The existing `/market-analysis` page says **ANALYSIS ONLY**,
SOURCE_RELATIVE_ANALYSIS and ABSOLUTE_RECENCY_UNKNOWN. It shows adapter state,
stream mode, exporter-session status, canonical sequence, pair status, transport,
processing age and each independently available analysis component. BOOTSTRAP,
WAITING, DISCONNECTED, REVOKED or pending pairs cannot project LIVE component
values. Browser responses still expire locally and clear on errors/visibility
changes. No fallback/demo values or execution controls are added.

Only 1m, complete 15m/1h buckets, trend, structure, liquidity patterns and FVG are
permitted. Absolute recency remains UNKNOWN; session authority UNKNOWN; news
UNCERTIFIED. Regime, confluence, confidence and decision remain NOT_PROJECTED.
LOCAL_PAPER is only a mode label. PAPER entries and SIM are DISABLED; LIVE is NO.
The adapter/API receive no execution interface and import no account/broker service.
Fault tests run with account/runtime/broker constructors prohibited. Order submit
is structurally unreachable through this API.

The Sprint 15T clock inventory gains the adapter's explicit clock calls and an
updated line for the modified profile. The Sprint 15X inventory regression removes
only these declared additions before checking the original assessment digest.
Existing clock readiness, reference bounds, timestamp tolerances and native
certificates are not promoted or rewritten. Sprint 15Y records the new source
fingerprints separately from the historical Sprint 15X report.

## Offline validation

Temporary-file tests distinguish bootstrap and live-tail, including a partial
startup line. They cover continuous appends through a completed hour; warmup;
partial writes and delayed pairs; missing/orphan/mismatched pairs; hashes;
duplicates/gaps/order; liveness; QPC epoch/regression/frequency/unavailability;
truncation/overwrite/replacement/rotation; closure; restart; unknown absolute,
session and news authority; API shutdown and no execution reachability.
Actual native clock reads and temporary-file sharing are tested; no NinjaTrader
stream is activated. Full regression and frontend results are in
`backend/tests/fresh_native_adapter_sprint15y.json`.

## Prepared operator procedure — not executed

1. Confirm readiness to start analysis-only observation and retain the compiled
   Sprint 15W `ArmsReadOnlyMarketV1`. Choose a fresh empty directory on the local
   fixed drive; retain the current Provider31 / NQ DEC26 / Minute 1 / CME US Index
   Futures ETH / UTC chart setup. No account or execution configuration is needed.
2. From the repository, run the explicit launcher using the approved Python
   environment. Substitute actual absolute paths; these are placeholders:

   ```powershell
   python -B -m tools.start_analysis_native_v1 --start-analysis-only --output-directory "C:\LOCAL\FRESH_RUN\inbox" --installed-exporter "C:\ACTUAL\NinjaTrader 8\bin\Custom\Indicators\ArmsReadOnlyMarketV1.cs"
   ```

   The default backend port is 8000 and dashboard origin localhost:3000. Use an
   available port matching the frontend's existing API origin; the launcher does
   not stop or replace an existing backend or edit frontend configuration.
3. Before activating NinjaTrader, inspect GET
   `http://127.0.0.1:8000/api/v2/market-analysis/time-profile` across multiple polls:
   ADAPTER_STATUS=WAITING, advancing adapter_heartbeat, exporter_session=null,
   market_stream=NOT_LIVE, zero analysis values and all execution authorities off.
   Confirm the chosen inbox is empty. The activation allowance is 15 nominal
   minutes from adapter construction. A timeout requires a new explicit start.
4. Only after the operator is ready, manually activate **one** exporter instance,
   supplying that output directory and ExpectedProvider=Provider31. No capture run
   UUID property is needed by this exporter; it generates its session UUID.
5. Open `/market-analysis` in the existing frontend. Expect BOOTSTRAP followed by
   LIVE_TAIL on a fresh paired boundary and source-relative values after warmup.
   Complete 15m/1h buckets require all constituent fresh minutes. Unknown absolute
   recency/session/news and disabled entries remain visible throughout.
6. On any revocation, stop using the analysis. Do not reuse or merge the old
   session. Diagnose the reason and establish a new explicit adapter baseline;
   no automatic recovery or native restart is performed.

No additional bounded pairing capture or NinjaTrader recompile is required for
the unchanged exporter. Offline readiness permits the next **adapter-start gate**;
it is not confirmation of a presently running service or native session. Native
activation readiness must be verified at step 3. LIVE MARKET PAPER SOAK remains
blocked. No human action to activate NinjaTrader is requested during this sprint.
