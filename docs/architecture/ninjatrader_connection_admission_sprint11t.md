# Sprint 11T: bounded startup and terminal connection revocation

## Decision and scope

Use a bounded STARTING phase followed by current-state-validated read-only
admission, with terminal event revocation. A callback never independently grants
readiness. This replaces immediate HELLO plus terminal treatment of every
startup contradiction. It does not declare any callback stale or superseded.
Only ArmsReadOnlyMarketV1 changes at runtime; reader, strategy, risk, thresholds,
observer and account/order interfaces are unchanged.

## Authorities and limits

Official references inspected for this decision:

- [Connection](https://docs.ninjatrader.com/ninjascript/connection_class): instance
  PriceStatus and Status expose price-feed and adapter/order-feed state. Requiring
  both Connected is a deliberately conservative ARMS read-only rule; Status
  grants no account or order authority.
- [ConnectionStatusEventArgs](https://docs.ninjatrader.com/ninjascript/connectionstatuseventargs):
  identifies the Connection and current/previous event statuses. Copy scalar
  values synchronously; do not log NativeError or private connection names.
- [OnConnectionStatusUpdate](https://docs.ninjatrader.com/ninjascript/onconnectionstatusupdate)
  reports changes. [Global subscription](https://docs.ninjatrader.com/ninjascript/connectionstatusupdate)
  documents subscription/cleanup, not an initialization replay barrier.
- [OnStateChange](https://docs.ninjatrader.com/ninjascript/onstatechange): Realtime
  is a data-processing lifecycle boundary, not proof of provider health. Data
  connection changes may affect script lifecycle. Resources must be cleaned up.
- [OnBarUpdate](https://docs.ninjatrader.com/ninjascript/onbarupdate) is tied to the
  Bars series and Calculate mode. [MarketDataEventArgs](https://docs.ninjatrader.com/ninjascript/marketdataeventargs)
  identifies the instrument, not a documented connection generation. Adding
  OnMarketData would create another subscription without resolving generation.

Read-only reflection of installed NinjaTrader.Core 8.1.8.2 confirms the public
metadata used by the exporter. ConnectionStatusEventArgs exposes Connection,
Error, NativeError, PreviousStatus, PreviousPriceStatus, PriceStatus and Status;
no generation or source-event timestamp is exposed there. Its type is a class.
MarketDataEventArgs likewise does not expose a connection generation. No native
connection/account object or getter was invoked for this inspection.

No documented guarantee of synchronous initial delivery, global/indicator
equivalence, callback drain completion, atomic multi-property reads, or a
provider generation token was found. No such guarantee is assumed. Two matching
samples detect observed instability; they do not prove uninterrupted physical
connectivity or eliminate changes between samples. Heartbeats prove local
exporter liveness plus contemporaneous status validation, not receipt of ticks.

## Candidate comparison

| Candidate | Safety and limitations | Decision |
| --- | --- | --- |
| A: existing callback-authoritative veto | Terminal containment, but HELLO precedes adjudication; startup contradictions are immediately fatal. Current-state validation outside events is weaker. | Replace for startup only; retain terminal uncertainty after admission. |
| B: bounded STARTING | No admitted history exists to preserve. Contradiction blocks admission; aligned event plus independent healthy poll permits a fresh boundary. Timeout and observed losses remain terminal. | Selected with C's revocation role. |
| C: pure current-state grant/event revocation | Ignoring a loss event because its current snapshot is Connected can conceal reconnect. Current state alone cannot erase loss evidence. | Reject pure version; keep loss events authoritative vetoes. |
| D: independent monitor/readiness latch | Same public metadata, plus cross-component ordering, stale latch and lifetime concerns. Observer cannot grant market admission. | Not needed; keep latch within exporter serialization boundary. |
| E: per-tick/source-generation authority | Would be stronger with a documented source epoch. Instrument-bound callbacks do not supply that contract here; closed-market ticks cannot be required. | No invented generation or additional subscription. |

## Startup and admission

1. On the first Realtime transition, pin exactly one registered futures-capable
   Connection, matching configured provider. Both current channels must read
   Connected twice. Reject ambiguous/missing source, Playback, configuration
   mismatch, unknown values and registry contention. A currently Connecting
   source is **not** admitted or waited through.
2. Open fresh UUID files. Remain STARTING: no HELLO, HEARTBEAT, FORMING or CLOSED.
   Sidecar diagnostics may appear before market sequence zero. No reader schema
   change is needed: diagnostics remain incompatible with market ingestion.
3. A known same-source Connecting callback while current samples are Connected
   keeps STARTING blocked. It does not count as an ignored/stale event or grant
   admission. Regression from prior Connected, reported loss, unknown identity
   or changing current samples stop immediately. All callbacks are recorded.
4. An aligned Connected event clears pending startup disagreement but **does not
   grant READY**. The next existing five-second heartbeat must independently
   revalidate registration, provider, chart configuration and both current
   channels. Only then, before 30 seconds elapsed, may HELLO and HEARTBEAT appear.
   Missing aligned event times out; there is no assumption one must arrive.
5. A monotonic 30-second startup deadline is enforced on callbacks/polls and by
   a one-shot thread-pool timer, independent of chart ticks/dispatcher progress.
   Scheduling or blocked native/I/O calls can delay cleanup; this is not a hard
   real-time guarantee. Admission at/after the deadline is prohibited.
6. Reanchor the candle boundary after readiness. Bars seen during STARTING are
   never buffered or replayed. Skip the first potentially partial admitted bar;
   require an entire subsequent observed bar before CLOSED. Existing downstream
   time/calendar/OHLCV/duplicate validation remains authoritative.

The observed 11S transition pair satisfies steps 3 and 4 as an input trace; no
claim about its original generation is needed. Before readiness there are zero
admitted candles or execution state whose continuity could be silently restored.
This is a new admission contract, not proof that the earlier callback was stale.

## Revocation and reconnect

Every bar and heartbeat checks current source again. Source removal/replacement,
additional futures source, registry contention, provider mismatch, either current
channel non-Connected, lifecycle departure/reentry, unknown state or instability
stops the session. Loss events stop even when current samples say Connected.
After READY, a callback with a non-Connected previous state also stops: a late
startup duplicate cannot be distinguished safely from reconnect. Healthy
Connected-to-Connected duplicates are harmless and retained in diagnostics.

STOPPED is terminal. No event, later healthy poll, timer callback or Realtime
reentry can revive the session. Fresh human-reviewed exporter/reader sessions
are required. No execution readiness is ever granted by this smoke path.

## Market closed and evidence

Connected status plus local heartbeats and zero candles is a legitimate
closed-market transport milestone. It does not certify price delivery, closed
1m bars, HTF bars or market continuity. Confirmed loss during closure still stops.
No fabricated tick/candle or calendar exception is introduced.

Prior 11S observation: 23 records, 14 heartbeats, 30.0018816 seconds, WINDOW_END,
NONE; all 44 samples/channel Connected. Global and indicator transition pairs
remain separate observations. Original native evidence is preserved privately.
The new policy is offline-tested, not yet natively activated.

## Verification and one materially new native experiment

Readiness-model tests ran before exporter changes. Whole-source tests substitute
only time/native host surfaces, and exercise actual startup, callbacks, emission,
bar suppression, current-state revalidation and cleanup. Native DLL compilation
uses installed assemblies without loading a provider or installing the DLL.
Existing Sprint 10/11 and MVP safety regressions remain required. Test environment
values match the existing V17 api_settings fixture; no production setting changes.

In NinjaScript Editor replace the ArmsReadOnlyMarketV1 body with the repository
source, preserve exactly one NinjaScript-generated wrapper, and Compile (F5).
Remove the finished ArmsConnectionObserverV1 from the chart. Remove the old
exporter and add **one** fresh exporter with NQ DEC26, Minute/1, application UTC,
CME US Index Futures ETH, ExpectedProvider Provider31, and output directory
`C:\Development\ARMS-AI\.arms-dev\ninjatrader-current` (separator before .arms-dev).
Keep it open at least 35 seconds. Preserve every existing evidence file.
Do not configure accounts or orders. No native installation is automated here.

Expected informative outcome: sidecar WAIT_STARTUP_ALIGNMENT then CONTINUE;
later HELLO plus periodic HEARTBEAT, or an explicit terminal reason. An empty
market file during STARTING is intentional. Attach a new reader only after
HELLO; attaching earlier can correctly hit its independent freshness deadline.
No market-open candle milestone is claimed by a closed-market retest.
