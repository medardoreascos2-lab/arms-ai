# Sprint 13 native timestamp investigation

Baseline `c56ec51be5eac28302216b1e99d07fe3eb7c53ae`. No rearm, chart change,
clock correction, account access, order action or native deployment occurred.
The canonical freshness/future-data gate and exporter remain unchanged.

## Findings and causal limits

Session `af10b6fe-8379-4f18-b3f4-bc296d14bfad` arrived within the activation
allowance. Startup passed; the watcher stopped on the first FORMING frame.
Its emission was 00:22:58.8210269 UTC, close label 00:24:00 UTC, hence
ordinary one-minute start 00:23:00 UTC. Python preserves this to microsecond
precision, yielding -1.178974 seconds. No timezone offset is added by the
reader. The exact sub-microsecond remainder cannot explain a second-scale gap.

Later untouched exporter evidence repeats the relationship on both FORMING
and CLOSED frames. In the prefix inspected at 00:27:40 UTC, five FORMING and
three CLOSED frames precede their relevant boundaries by 0.276106 to
1.232827 seconds. These later records were inspected read-only; none was
backfilled into certification. This is not solely a historical-to-realtime
first-bar effect or confusion about an upcoming FORMING close label.

Independent read-only `w32tm /stripchart /dataonly /samples:3` measurements:

| Reference | Local observation interval, UTC | Reported offsets, seconds |
|---|---|---|
| time.windows.com | 00:26:51–00:26:55 | +1.3728026, +1.3748611, +1.3762588 |
| time.cloudflare.com | 00:27:14–00:27:18 | +1.3720453, +1.3746314, +1.3774701 |

The workstation clock was behind both references by approximately 1.37
seconds. Windows Time was Stopped, startup mode Manual; `/query /status`
returned service-not-started 0x80070426. No service or clock was changed.
These measurements confirm current clock skew and strongly support the causal
explanation. They are later, unauthenticated network time observations, not a
measurement of the exact original tick or a time-authority certification.
Provider31's original tick timestamp and the host's Core.Globals.Now at that
callback were not recorded. Exact tick-by-tick attribution therefore remains
unproven. Do not use these offsets to shift any saved or future candle.

## Semantic audit

- **BAR_LABEL_SEMANTICS:** NinjaTrader uses the closing boundary as an intraday
  minute bar label. [How Bars are Built](https://ninjatrader.com/support/helpguides/nt8/how_bars_are_built.htm)
  also describes provider timestamps versus PC timestamps when none is supplied.
- **TIME0:** [Time[0]](https://docs.ninjatrader.com/ninjascript/time) is the current
  bar's timestamp, not callback arrival time or an independently synchronized clock.
- **Installed behavior:** `@MinuteBarsType.cs`, SHA-256
  `64f0d2960217dc9ae23bd29f7d0a1c62e3bb22fb5909e0608e1ef53e83461bd4`,
  assigns realtime tick-based input to the next minute boundary using session
  anchoring and floor arithmetic; prebuilt bar input uses ceiling arithmetic.
  Exact-boundary ticks begin the following minute. Session-end clipping exists;
  the observed ordinary midnight-UTC interval is not near that boundary.
  This audits installed source; the stream does not attest its loaded binary hash.
- **FORMING_BAR_SEMANTICS:** A forthcoming close label is normal while its
  minute is forming. A bar start later than callback wall time is the conflict.
  The existing gate already subtracts exactly one minute from CLOSE labels;
  it does not reject merely because a forming close lies in the future.
- **Calculate / transition:** [OnEachTick](https://docs.ninjatrader.com/ninjascript/calculate)
  runs per realtime tick; historical OHLC bars normally run at bar close.
  The exporter checks State.Realtime and [IsFirstTickOfBar](https://docs.ninjatrader.com/ninjascript/isfirsttickofbar),
  then skips the first partial interval before exporting a completed bar.
  It emits FORMING only at those first-tick callbacks, not on every tick.
  A new tick signals the preceding bar's close; a PC timer does not construct it.
- **TIMEZONE_CONVERSION:** HELLO asserts UTC and SafeSource checks the native
  application timezone. `SpecifyKind(Time[ago], Utc)` changes Kind, not ticks;
  it is not an exchange-to-UTC conversion. The loaded calendar independently
  demonstrated UTC iterator boundaries despite the PC's Eastern display zone.
  The template is Chicago/Central; no hours-scale timezone error is observed.
  Original Time[0].Kind is absent, so do not claim every native conversion proved.
- **READER_NORMALIZATION:** `_utc` requires explicit zero offset; CLOSE remains
  CLOSE. Provider naming normalization has no timestamp arithmetic.
- **CURRENT_CANDLE_AUTHORITY:** FORMING requires emission at/after implied start;
  CLOSED requires emission at/after close. The reproduced FORMING rejection is
  STALE_DATA; an early CLOSED frame is TIME_SYNC_INVALID. Neither grants a
  runtime/account initialization or execution side effect.
- **HARNESS_ASSUMPTION:** It correctly uses the canonical gate, but the host UTC
  clock must be trustworthy. A valid calendar hash does not certify wall-clock
  synchronization. Its generic recovery fault masks the inner timing reason;
  this investigation reproduces that reason without changing live admission.
- **UNKNOWN:** Original tick timing, Core.Globals.Now relationship to UtcNow at
  capture, and exact provider-versus-host skew at the failed callback.

## Bounded observer design, not deployed

Only if exact source attribution remains necessary after the clock issue is
reviewed: use a separate observation-only indicator for 180 seconds maximum,
1024 records maximum, one new private file, auto-close on deadline/termination.
Do not replace or change the current exporter. Keep no account/order references.

Record START/END, monotonic elapsed time and sequence, lifecycle state, UTC
wall time before/after each sample, raw Core.Globals.Now with Kind (not claimed
independent UTC), application/system/template timezone IDs, provider enum,
contract and Minute/1 metadata. In OnBarUpdate only, record CurrentBar,
IsFirstTickOfBar, Time[0], Bars.GetTime(CurrentBar), both raw Kinds and ticks.
Derive UTC only using a known native timezone contract; retain UNKNOWN if it
cannot be established. A separate derived ordinary close-minus-one-minute
boundary is labeled a comparison, never substituted for the native timestamp.

In OnMarketData, record Last event Time and Kind plus local receive UtcNow and
monotonic receive order, with price-valid/finite flags rather than prices or
bulk OHLCV. Correlate callbacks conservatively: no assumption of one-to-one
identity based solely on arrival order. [OnMarketData](https://docs.ninjatrader.com/ninjascript/onmarketdata)
documents expected ordering, while [MarketDataEventArgs](https://docs.ninjatrader.com/ninjascript/marketdataeventargs)
does not guarantee that every provider's Time is exchange-authenticated UTC.
Record unknowns instead of relabeling. Rate-limit steady Last samples to one
per second, retain adjacent first-bar samples, count omitted samples explicitly.
No bulk market dump, private strings, credentials, paths or account identifiers.
Independent read-only time-service samples should bracket this future observer.
Compilation/testing would be required before deployment; no operator activation
is requested by this investigation.

## Disposition

Runtime timestamp correction is not justified. Regression additions are
justified: reproduce the observed offsets, accept legitimate future *close
labels* for currently forming bars, and retain zero tolerance for future
starts, closed candles and event emissions. No sleeps or timestamp adjustments.

Resolve workstation time synchronization through a separately authorized
operational action, then verify independent offsets and fresh native timing.
Do not correct the running chart's evidence retrospectively. Do not rearm the
125-minute harness or ask for remove/re-add now. A synchronized-clock retest
is pending, and exact tick attribution may require the observer above.

Microsoft's [Windows Time tools reference](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)
describes stripchart as an offset measurement; the diagnostic commands used
here do not resynchronize the clock.
