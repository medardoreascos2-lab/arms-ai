# Sprint 15U: clock evidence acquisition and analysis gate

Baseline: `de52c6c1392440f1e3d56b360bca50ed52ac4918`.
The acquisition tool is separate from runtime. It cannot initialize market,
paper, account, or broker services. Windows settings, Sprint 15T, the existing
exporter, reader, candle authority, calendar, and timestamp tolerances are unchanged.

## Finding

Repeated small offsets do not supply the four missing Sprint 15T inputs.
Cloudflare and Google are separately operated references reviewed for measurement,
not independent attestations of a finite absolute UTC error. Google explicitly
provides no accuracy commitment and uses smear; Cloudflare does not smear.
Therefore their agreement cannot establish zero common-mode error, and a leap
policy difference must be covered by any reviewed UTC-error bound. Querying them
does not configure or mix them as Windows synchronization peers.

NTP root delay/dispersion and precision are recorded server claims. Origin echo
and a connected UDP socket reject mismatched replies but do not authenticate the
time source. This is the existing Sprint 15T provenance requirement, not a new
requirement introduced to block analysis. No measured offset, lowest RTT, stratum,
or finite observed drift maximum is automatically converted into ReviewedBounds.

## Evidence inventory and acquisition

| Datum | Source and measurement | Unit | Freshness | Trust/uncertainty | Sprint 15T input |
| --- | --- | --- | --- | --- | --- |
| Reference timestamps | 12 concurrent rounds to Cloudflare, Google and current Microsoft peer; validate server/version/LI/stratum/origin, retain raw packets | integer ns; outward conversion to us | sample monotonic age recorded individually | UDP unauthenticated; absolute reference error remains unreviewed; LI=0 does not exclude Google smear | Sample R2/R3; ReferenceBound still needs separate reviewed finite error/provenance |
| Host UTC and transport | QPC-backed perf counter brackets each `time_ns` read surrounding send/receive | ns and us | one new process epoch; no old sample reuse | bracketing includes scheduling; wall quantization and monotonic rate require reviewed bounds | Sample H1/H4/M1/M4; capture_error must include brackets, quantization and outward conversion |
| RTT/asymmetry | outer monotonic elapsed bracket; conditional receipt enclosure `[R3, R2+d]` | ns | per exchange | whole path delay may be either direction; midpoint +/-d/2 is diagnostic and conditional on exact reference/rate | full causal interval, never symmetric-path assumption |
| Disagreement | representative offsets plus every retained raw sample | ns | same bounded run; samples are concurrent, not exactly simultaneous | low-delay median is display-only, no sample is dropped from future proof inputs | assess all references/samples; mismatch UNKNOWN |
| Drift | paired wall/mono changes, reference offset slope and GetSystemTimeAdjustment per round | ppb; adjustment/increment in 100 ns; ppm | about 55 seconds of samples, scoped to this capture | empirical endpoint slope does not bound excursions, future drift, suspension or monotonic absolute rate | ReviewedBounds.rate_error_ppb remains missing |
| W32Time | `/query /status /verbose`, `/peers /verbose`, `/configuration`, service State/StartMode before/after | raw local wall strings, scalar states | bounded query brackets | last-sync wall string is not an independently proved mono instant; denied queries remain unavailable | WindowsState.last_sync_mono_us remains null until mapped with reviewed uncertainty |
| Native emission | existing session/sequence/HELLO and event_time/raw close label | 100 ns UTC string | immutable raw row identity, source file/hash/offset | no paired native monotonic observation; applying today's offset to an old row is invalid | interval for source E requires mapping/provenance |
| Native/reader pairing | proposed callback pair and complete-line read brackets | QPC ticks/frequency, 100 ns UTC | one process/boot epoch, connection lifecycle, calendar hash | no sibling-callback equivalence; no reusing restart/reconnect evidence | reviewed E/R/current intervals and epoch |
| Operation window | source CLOSE label plus unchanged freshness and certified ordinary-open calendar | integer UTC us | each record, each proof horizon | no current window fabricated from arrival time; session boundaries half-open | OperationWindow for MARKET_ANALYSIS only |

Run the collector explicitly as:

```powershell
py -B -m tools.clock_evidence_v1 --output <new-private-output-file>
```

The parent directory must already exist. Exclusive creation prevents overwrite.
The collector makes at most 36 small NTP requests (three per round), uses a
three-second child-process DNS timeout and two-second UDP timeout, and queries
Windows with five-second process timeouts. A 12-by-5-second monotonic schedule
measures drift; pacing is not market admission, boundary compensation or a clock
adjustment. OS scheduling is not a real-time duration guarantee. There is no
service restart, resync, registry write, provider mutation or new dependency.
Private raw output stays outside Git. Public reports expose no account/provider
credentials. Process capture UUID is not falsely labeled an OS boot attestation.

The bridge passes actual decoded Sample objects into the unchanged `assess` with
missing ReviewedBounds/state mapping/windows. Expected result is UNKNOWN. This
explicit negative result closes the misleading-offset-PASS path, but does not
claim to have closed the trust gap. Bounds cannot be selected to pass this host.

## Native timing witness design (not installed or compiled)

Existing HELLO, sequence, UTC emissions, labels, OHLCV and native certificate can
be reused for configuration/semantics. They cannot recover a missing monotonic
callback pair. A fresh file reader can bracket receipt of each complete raw line
and retain byte offset/hash; reading an old line cannot establish live receipt.

The smallest proposed diagnostic indicator records only the first realtime tick
of each new primary Minute/1 bar and the associated transition state. At callback
entry it captures `Stopwatch.GetTimestamp`, `DateTime.UtcNow.Ticks`, then QPC
again, recording frequency and a fresh epoch. It copies scalar `CurrentBar`,
`BarsInProgress`, first-tick flag, native Time[0]/Time[1] and Kind, GetTime for
the matching index, periods, checked UTC application zone, native template zone,
session begin/end/trading date and calendar hash. It never relabels Unspecified
native time without the reviewed configured-zone conversion. It rejects wrong
configuration, historical callbacks, unknown continuity and reconnects.

If price-event timing is needed, a bounded OnMarketData scalar sample preserves
native event time/Kind and its own paired callback receipt. Platform ordering
between event types or different indicator instances is not a common atomic
callback identity. Provider event time is not presumed authenticated exchange UTC.
No account registry, account object, order operation, connection change, new data
series or synthetic market data is part of this design. Use a monotonic deadline,
bounded records, fresh private file, fixed error codes and detached timers on end.

Crucial limitation: another indicator's callback, even with an identical bar,
does not timestamp ArmsReadOnlyMarketV1.Emit's exact UTC read. Do not set the
offline `callback_bound_to_exporter_record` prerequisite from bar-label equality.
The exact native record must instead be bound by one of these reviewed methods:

1. Reuse the original emitted H with a continuous, valid, positive-rate,
   no-step host-wall/QPC mapping to enclose its emission M, anchored to the same
   verified process/boot epoch. This requires the missing drift/step/capture proof;
   a finite sampled trace alone does not prove no intervening step.
2. An exact in-process emission hook reviewed separately. Editing the existing
   exporter is prohibited in this sprint, so this option is not implemented.

The schema in the JSON artifact specifies the bounded observer and reader fields.
It is deliberately a design, not an uncompiled native source claimed certified.
The Python native-candidate checker tests the proof obligations under explicit
synthetic reviewed assumptions; its true binding flag is not a runtime attestation.

## Operation windows and quarantine decision

For an ordinary full minute ending C, age A=30 seconds in the unchanged authorized
profile, and certified open interval [O,X), the candidate CLOSED current-time
window is `[C, C+A] intersect [O,X)`. FORMING starts C-60 seconds and ends C+A.
Require the entire minute to belong to the reviewed session. The helper rejects
clipped/unreviewed minutes; calendar coverage cannot be inferred from this helper.
The whole projected true-UTC interval must be contained, with X always excluded.
Event/receipt/now ordering and unchanged transport/receipt/close age conditions
are checked separately. No positive fixed maximum offset is inferred.

| Operation | Required proof and current eligibility |
| --- | --- |
| MARKET_ANALYSIS | Source semantics, paired timing, reference/rate bounds, per-record freshness, current certified session containment and unchanged native/reader gates. Potentially eligible only after these are proved. |
| LOCAL_PAPER (model key PAPER) | Same market proof plus reviewed news blackout coverage, risk and explicit entry authority. NEWS_UNCERTIFIED and PAPER_DISABLED remain blocking regardless of clock result. |
| NEWS | Certified calendar/event coverage and complete pre/post blackout containment. No empty-calendar or instantaneous-event clearance substitute. |
| SIM | Separate account identity/execution timing contract absent; UNKNOWN/DISABLED. |
| LIVE | Separate venue/execution timing contract and authorization absent; NO. |

Quarantine is not objectively required by measured lag alone. Safely post-boundary
proven observations require no queue; uncertain observations remain rejected.
Tests show that later receipt/evaluation cannot cure an emission interval crossing
the close boundary. Introducing a queue would not create missing reference/drift
or native provenance. Runtime quarantine is therefore not implemented. There is
no release path, canonical insertion, duplication, changed label or fabricated bar
in this work. Existing duplicate/HTF/continuity regressions remain applicable.

## Short capture plan and stopping point

After reviewed bounds and a viable native-emission binding method are available,
prepare a diagnostic-only reader with an exclusive namespace, snapshot all old
files/prefixes, pin process/source/calendar identities, and monitor fresh complete
lines with paired receive brackets. Start reference acquisition before native
activation and keep its reviewed validity through the last record. Never reuse
the Sprint 15S 7,500-second ingestion launcher as a clock diagnostic.

A proposed maximum 330-second capture, with a fresh 180-second activation deadline,
targets three consecutive full realtime CLOSED minutes and matching FORMING
boundaries. The unchanged exporter skips its anchored first realtime bar: the
first CLOSED arrives at callback index +2 and the third at +4. Budget 30 seconds
for existing startup, up to 60 for first-callback alignment and four minute
transitions (240 seconds). This is an observation budget, never a timestamp
tolerance. Stop as soon as those proofs are complete or at the deadline. It may
be INCONCLUSIVE on low activity or missing source alignment. This establishes
only sampled ordinary-open timing, not future rate bounds or new HTF/session
certification; the previous certified HTF path is reused. No repeat 7,500-second
capture is justified to solve these timing inputs.

No native watcher is launched while its evidence method remains unproved. Do not
ask the operator to remove/re-add anything. A later ready reader must independently
report ACTIVE_AND_WAITING and its fresh deadline before any human native activation.
This sprint makes no claim that a waiting file alone proves a live reader process.

## Fresh measurement

The bounded acquisition ended at host UTC 2026-09-21 06:49:38.183006. All three
references returned 12 valid replies. Low-delay median reference-minus-host
offsets were Cloudflare +0.0952520875 s, Google +0.0972893275 s and Microsoft
+0.098619174 s. These are diagnostics across the sampling interval, not an exact
current offset or an authorization lease. Representative disagreement was about
3.37 ms; maximum retained RTT was 218.4 ms. No outlier was removed from raw evidence.

W32Time remained Running/Auto on time.windows.com,0x8 in Sync. A scheduled sample
occurred during observation: reported last sync advanced from 02:32:16 to 02:49:20
local and last-sync error changed from 2 to 0. Reported phase offset changed from
89.7266 to 76.0262 ms. The read-only adjustment API reported nominal +25.6 ppm
throughout. Endpoint host/QPC rates were approximately +28.86 ppm; these observations
are not a rate ceiling. No manual resynchronization was performed. The packet,
Windows-query and paired-read evidence is retained privately with its SHA256 in
the JSON artifact. The unchanged formal preflight returned UNKNOWN.

Backend health and frontend page independently returned HTTP 200. The dashboard
still reports PAPER_DISABLED, NEWS_UNCERTIFIED, no native account access, zero
broker calls, SIM disabled and LIVE false; genuine current market data is not
attached. No observation was fabricated to populate it.

## Validation and proposed commit scope

The complete 58-module selection passed 1,918 tests, including the Sprint 15T
suite, the 70 new Sprint 15U cases, and the existing private Sprint 15S
analysis/news cases. The earlier focused Sprint 15T/15U run passed 650 tests;
counts overlap. Selection is the existing 55-module Sprint 15T regression list
plus `backend/tests/test_clock_evidence_sprint15u.py`,
`.arms-dev/sprint15s/test_analysis_only.py` and
`.arms-dev/sprint15s/test_news_limits.py`. The unchanged reviewed test_environment
profile and existing private dataset map were used. One pre-existing
Starlette/httpx deprecation warning remains. No production entry flag was enabled.

Frontend: all four `src/lib/*.test.mjs` suites passed 32 tests; `npm run lint`
passed. `next build --webpack` passed on a fresh private copy of all 67 tracked
frontend files using existing dependencies, preserving the active dashboard.
No frontend source, native source or clock preflight runtime/model changed.

Only these four new files are proposed for a later expressly authorized commit:

- `tools/clock_evidence_v1.py`
- `backend/tests/test_clock_evidence_sprint15u.py`
- `backend/tests/clock_evidence_sprint15u.json`
- `docs/architecture/clock_evidence_sprint15u.md`

The prior explicit one-commit authorization covered Sprint 15T and was consumed.
Sprint 15U does not stage or commit without current-phase authorization under
AGENTS.md section 11. No push, amend or history operation is performed. Private
raw acquisition, test reports, build copy and old evidence are not proposed for Git.

## Sources reviewed

- [Cloudflare NTP and non-smear policy](https://developers.cloudflare.com/time-services/ntp/).
- [Google NTP limitations, smear and no NTS](https://developers.google.com/time/faq).
- [RFC 5905 packet, timestamps and error model](https://www.rfc-editor.org/rfc/rfc5905.html).
- [Microsoft QPC behavior](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps).
- [Microsoft clock-rate observation API](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-getsystemtimeadjustment).
- [NinjaTrader bar close labels](https://ninjatrader.com/support/helpguides/nt8/how_bars_are_built.htm)
  and [OnMarketData ordering](https://ninjatrader.com/support/helpguides/nt8/onmarketdata.htm).

These sources document mechanisms and service limitations, not an attestation
of this workstation's current UTC error. The justified next step is review of
a concrete finite reference/rate provenance contract and the immutable-emission
mapping. No Windows adjustment or ARMS gate relaxation is proposed.
