# Sprint 11S: bounded connection observer

## Purpose and boundary

`integrations/ninjatrader/ArmsConnectionObserverV1.cs` is a separate, temporary
diagnostic indicator. It records connection metadata only. It does not modify,
invoke or revive `ArmsReadOnlyMarketV1`, and has no accounts, orders, ATI,
strategy, market-series processing, transport admission or execution interface.
Its JSONL schema is deliberately incompatible with the market reader.

Contradictions, loss, unknown values and duplicate callbacks are **observations**,
not admission decisions. They do not stop this diagnostic. They continue to stop
the unchanged exporter under its existing policy. This distinction grants no
trading or market-data authority.

## Collection and limits

On DataLoaded, the observer opens one new UUID-named `.observer.jsonl` file in an
explicit existing local directory, pins exactly one Connection matching the
configured provider enum, and subscribes to global ConnectionStatusUpdate.
Selection does not require Connected: Connecting/Disconnected states are useful
evidence. Zero or multiple matches leave the source unselected, with an explicit
NO_PROVIDER_MATCH or AMBIGUOUS_PROVIDER_MATCH diagnostic. It never silently
rebinds if another matching object appears later.

Registry reads use a non-blocking lock attempt to avoid waiting for a provider
thread that might itself be delivering a callback. A busy registry records
REGISTRY_UNAVAILABLE, not a guessed membership or a source change. At startup,
that leaves the source unselected for this capture. During capture the nullable
`source_registered` field is null when membership could not be observed.

Capture lasts **30 seconds**, measured by Stopwatch. Thread-pool timers provide
two-second observation heartbeats and a separate one-shot deadline. No tick or
UI dispatcher is needed. Every observation checks the deadline, including again
after collecting its snapshot. At the first callback at/after the deadline, only
OBSERVER_END may be emitted. OS scheduling or blocking filesystem/native calls
can delay actual cleanup; this is not a hard real-time deadline. The end record
reports actual elapsed time rather than concealing an overrun.

A second bound limits the file to **512 records including START/END**. A storm
ends capture with RECORD_LIMIT; that capture is truncated, not a successful
30-second observation. No events are silently deduplicated or coalesced.

On timeout, host termination, record limit or infrastructure failure, cleanup
latches once, unsubscribes the global handler, disposes both timers and closes
the writer. Queued callbacks after cleanup cannot write or restart it. Native
callback contradictions alone never trigger cleanup. An I/O failure may prevent
the END record from being written; a missing end cannot certify completion.

Resources are created at DataLoaded, not SetDefaults: opening a NinjaTrader
indicator picker can create preview instances that must not write files.
Callbacks before DataLoaded are not captured. Recordings cover the observer's
own indicator startup and globals delivered during that window, not events that
predate its subscription or another indicator's private callback invocation.

References: [NinjaTrader lifecycle](https://docs.ninjatrader.com/ninjascript/onstatechange),
[global connection subscription](https://ninjatrader.com/es/support/helpguides/nt8/connectionstatusupdate.htm),
[callback arguments](https://docs.ninjatrader.com/ninjascript/connectionstatuseventargs).
These APIs permit observation; they do not establish a supersession guarantee.

## Record contract

Schema: `arms.nt.connection-observer.v1`. Records are START, LIFECYCLE,
CONNECTION_STATUS, OBSERVATION_HEARTBEAT or END. CHANNEL distinguishes INDICATOR,
GLOBAL, TIMER and LIFECYCLE. A global event and an indicator callback with equal
values remain separate observations; they are not automatically equated.

Every frame includes:

- Session UUID and monotonically increasing observation sequence.
- UTC serialization and callback-entry times, plus monotonic elapsed milliseconds
  for each. Entry order can differ from serialized order across threads; these
  timestamps are not provider event-creation timestamps.
- Native indicator lifecycle state and observer state OBSERVING or ENDED.

Non-END payloads contain:

- Callback current/previous price and adapter states; callback presence.
- Two selected-source price and adapter samples; agreement and known-state flags.
- Same-source identity, provider enums, selected-source presence and registration.
- Pinned identity status and initial selection outcome.
- `observation_only=true`; no accepted/execution/admission field exists.

Heartbeat/lifecycle records have no callback, so callback fields are UNKNOWN.
Two UNKNOWN samples may agree textually; `samples_known=false` prevents treating
that as proof of health. Unknown enums, null options and getter exceptions use
UNKNOWN, never provider-owned exception text. Private connection names, account
identifiers, machine/user paths, credentials, NativeError and stack traces are
not read or serialized. A session UUID is an observation identifier only.

END records contain a fixed reason/error category and the capture limits. A
normal completed window ends with WINDOW_END. HOST_TERMINATED and RECORD_LIMIT
must be distinguished from a full window. Metadata is written with CreateNew,
UTF-8 without BOM, read sharing and autoflush. Existing evidence is untouched.

## Offline verification

The entire C# source is compiled and run with a metadata-only NinjaTrader test
surface. Only Stopwatch and Timer bindings are replaced for deterministic time;
observer method bodies are unchanged. The stub API offers no order, account or
market-series operations; static checks also exclude reflection, dynamic calls,
network/process APIs and connection-control commands.

Tests cover contradictions followed by additional callbacks, duplicate retention,
global/indicator channels, 14 scheduled heartbeats through 28 seconds, automatic
END at 30 seconds, either timer winning the deadline, record limits, early host
termination, queued callbacks after disposal, I/O failures, cleanup exceptions,
provider/source mismatch/removal/replacement, missing/ambiguous sources, unknown
enums/options, read failures, unstable samples and registry contention at startup
and during callbacks. Tests also pass observer frames
to the real market reader and require rejection with zero candles/runtime/order
authority. These are simulated timing tests, not a native observed milestone.

## One human activation

Do not replace or reconfigure ArmsReadOnlyMarketV1. Do not configure accounts or
perform order actions. Preserve all existing `.jsonl` and `.connection.jsonl`
files. The observer source has been compiled offline against installed native
assemblies; automatic native installation is not performed.

| WINDOW | MENU | FIELD | VALUE | BUTTON |
| --- | --- | --- | --- | --- |
| NinjaTrader Control Center | New > NinjaScript Editor > Indicators > right-click New Indicator | Name | ArmsConnectionObserverV1 | Generate |
| NinjaScript Editor | ArmsConnectionObserverV1 source tab | Source | Replace wizard source with repository `integrations/ninjatrader/ArmsConnectionObserverV1.cs`; keep only one generated wrapper | F5 / Compile |
| Existing NQ DEC26 chart | Right-click > Data Series | Instrument / Type / Value / Trading hours | NQ DEC26 / Minute / 1 / CME US Index Futures ETH; keep application timezone UTC | OK |
| Chart | Right-click > Indicators > ArmsConnectionObserverV1 | Expected provider enum | Provider31 | Add |
| Same indicator properties | ARMS observer | Private observation directory | `C:\Development\ARMS-AI\.arms-dev\ninjatrader-current` | OK |

Leave that **one** observer instance in place for at least 35 seconds. It should
end automatically after its 30-second capture; do not re-add it. Its fixed output
line should indicate `ARMS_CONNECTION_OBSERVER_END reason=WINDOW_END error=NONE`.
After completion remove only this observer from the chart; keep its evidence
file. If it ends with another reason, preserve the file and report the category;
do not repeat the experiment automatically. No manual JSONL copying is needed.
The path includes the separator before `.arms-dev`; the sibling path
`ARMS-AI.arms-dev` is not the established evidence directory.

## Post-observation adjudication

First verify schema, session/file identity, contiguous sequence, elapsed bounds,
end reason, source selection, sampling consistency and callback/lifecycle order.
Keep all sessions separate. A closed market permits zero ticks and candles;
absence of candles is irrelevant to this metadata-only experiment.

Use the evidence to distinguish:

- CURRENT_CONNECTION_IN_PROGRESS: selected current price remains Connecting.
- CURRENT_CONNECTION_LOST: selected current price reports ConnectionLost or
  Disconnected. Report the API state; do not infer physical network cause.
- UNSTABLE_CONNECTION_STATE: changing samples, source registration/identity or
  inconsistent source/provider evidence.
- PROVEN_SUPERSEDED_STARTUP_TRANSITION: only with sufficient connection-specific
  ordering/generation proof, not merely a later Connected callback or repeated
  equal samples. This observer does not invent that proof.
- INSUFFICIENT_EVIDENCE: incomplete/ambiguous capture, missing selection, unknown
  state or unresolved ordering. Connected throughout may be reported as an
  observation while supersession remains insufficiently established.

Global and indicator correlation can distinguish hypotheses better than the old
exporter, which stopped recording on the first mismatch. It still cannot recover
events preceding subscription, establish an atomic provider snapshot, create a
provider generation identifier or prove that equal callbacks represent one native
event. No automatic policy change follows from this capture. Market-open candle
certification, SIM discovery and execution remain gated separately.
