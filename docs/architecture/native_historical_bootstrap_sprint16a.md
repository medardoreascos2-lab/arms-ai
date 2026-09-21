# Sprint 16A — isolated native historical bootstrap

Offline implementation and SDK compilation are complete. No historical capture,
NinjaTrader installation, live warm-up injection, service restart or deployment
was performed. The eight completed minutes from Sprint 15W remain the only
previously reviewed native bootstrap archive. Synthetic tests are not additional
native market evidence.

## Source audit and choice

| Mechanism | Finding | Decision |
| --- | --- | --- |
| Chart-loaded Bars / ChartBars | Tied to the chart's data-series configuration and loaded depth. A display range is not a provenance boundary. | Do not change or read the active production chart for extraction. |
| Existing indicator Bars collection | Supported absolute-index OHLCV access after DataLoaded. Inherits its input series. | Useful accessors, but does not independently establish unmerged DEC26 acquisition. |
| State.Historical OnBarUpdate | A historical processing state, not a separate source; historical OHLCVT does not reconstruct original tick receipts. | Do not modify the live exporter's state handling or present historical callbacks as live. |
| BarsRequest | Independently specifies instrument, minute period, trading hours, merge and lookup policies. Date requests encompass trading days, not an exact intraday cutoff. | Selected: one-shot Repository lookup and DoNotMerge. |
| AddDataSeries / BarsArray | Adds a hosted series and lifecycle/loading requirements. | Unnecessary coupling for a diagnostic snapshot. |
| ReloadAllHistoricalData | Reloads matching chart series and transitions scripts again. | Explicitly excluded; violates preservation of the current runtime. |
| Binary repository parsing / arbitrary CSV | No reviewed extraction/provenance contract here. | No fallback. |

Official references: [BarsRequest](https://docs.ninjatrader.com/ninjascript/barsrequest),
[request MergePolicy](https://docs.ninjatrader.com/ninjascript/barsrequest_mergepolicy),
[Bars](https://docs.ninjatrader.com/ninjascript/bars),
[ChartBars](https://docs.ninjatrader.com/ninjascript/chartbars),
[historical Calculate behavior](https://docs.ninjatrader.com/ninjascript/calculate),
[BarsArray](https://docs.ninjatrader.com/ninjascript/barsarray),
[SessionIterator](https://docs.ninjatrader.com/ninjascript/sessioniterator),
[GetNextSession](https://docs.ninjatrader.com/ninjascript/getnextsession),
[ReloadAllHistoricalData](https://docs.ninjatrader.com/ninjascript/reloadallhistoricaldata).

Installed NinjaTrader.Core/Gui 8.1.8.2 and their XML documentation were inspected.
The new authored indicator compiled with the installed .NET Framework compiler
and SDK, using a standalone IndicatorBase shim. The resulting assembly was only
inspected with ReflectionOnlyLoad; it was never loaded into NinjaTrader or
instantiated. SDK compile is not a native capture or installed wrapper test.
The certificate records source/reference hashes and the complete compiled Cbi
call list: instrument metadata and a playback-presence guard only.

## Export contract

`ArmsHistoricalBootstrapV1` is a separate, default-disabled indicator. It makes
one `BarsRequest` with NQ DEC26, Last, Minute/1, CME US Index Futures ETH,
DoNotMerge, Repository, reset-on-new-trading-day, no split/dividend adjustment.
It rechecks request and returned-series identity. It neither subscribes to Update
nor requests provider downloads. Repository lookup cannot attest which provider
originally supplied cached bars: `provider_attribution=UNATTESTED` is mandatory.
The current Provider31 connection does not establish historical Provider31 origin.

The configured application timezone must already be UTC; playback must be absent.
Native bar and iterator timestamps must actually have DateTimeKind.Utc. They are
never relabeled from Local/Unspecified. This is a capture prerequisite to verify
on real output, not an assumption that SDK compilation proves timestamp behavior.
Documentation describes iterator local-time values; a non-UTC observation fails
closed even if the application configuration says UTC.

The first and last returned bars are excluded conservatively. Every exported row
has an absolute source index, dataset UUID, identity, historical classification,
UTC minute CLOSE label and validated OHLCV. A final close seal binds the exact
UTF-8 JSONL bytes, row count and SHA-256. Partial files without a seal are rejected.
Only a fresh empty, local fixed-drive, non-reparse directory is accepted. Counts
are bounded to 10,000 exported bars. Requests span at most fourteen date intervals;
this upper bound is not a promise that every fourteen-day request fits the count
limit. Start with seven days plus the current partial day.

DoNotMerge excludes silent SEP26 substitution and back-adjustment in this request.
It does not authenticate the repository against manual edits/imports. Bundle
hashes bind bytes; operator-controlled acquisition remains the trust boundary.

## Certification and calendar

`arms.certified-native-history.v1` is separate from the Sprint 15Z sealed-production
schema. `certify_bootstrap` dispatches to its strict validator without relaxing
the existing production validator. The bundle embeds raw history, seal and static
template bytes and pins the reviewed exporter. Every load verifies an independently
reviewed whole-bundle SHA-256; a calculated hash alone is not provenance approval.

The immutable result contains ordered frozen bars, gap tuples and bounded calendar
coverage. Validation rejects duplicate/out-of-order labels, wrong/mixed identity,
invalid/unticked prices, invalid volume, adjusted history, unsupported SDK/source,
native timestamp kinds, stale/corrupt seals and unbound calendar definitions.
Zero volume is valid. No bars are interpolated or filled.

The pinned static ETH XML is stored as escaped UTF-8 text in a JSON fixture so
checkout line-ending conversion cannot change its original byte hash. That file
is calendar configuration, not a native bar capture. The captured SessionIterator
intervals must match independently derived pinned-template intervals over the
entire bounded range, including trading-day dates. Supported 2026 weekly sessions,
full holidays and early closes are checked; unsupported exception shapes or
coverage extending outside 2026 remain unknown and reject. Calendar coverage
extends from requested-from minus two days through requested-through plus eight
days; this limits the usable request dates near year boundaries.

* EXPECTED_SESSION_GAP: every missing minute lies outside verified open intervals;
  the following complete candle is inside an open interval.
* UNEXPECTED_DATA_GAP: at least one missing minute intersects an open interval.
* UNKNOWN_GAP: missing/mismatched calendar evidence, unsupported scope, or an
  unproven following candle. Unknown gaps never become expected by inference.

Expected closures are accepted and reported. Incomplete HTF buckets remain
incomplete across all gap types. Historical calendar proof never grants current
SESSION_AUTHORITY, ABSOLUTE_RECENCY, NEWS_AUTHORITY or execution permission.

## Actual warm-up requirements

Production `MarketAnalysisTimeProfileV1` uses the existing completed-bar aggregator
and `TrendEngineV2`: EMA10/EMA50, slope lookback 5, sideways threshold 0.0005.
The trend engine requests max(50, 5) = 50 completed candles. No periods changed.

| Projection | Minimum complete inputs | Minimum constituent 1m bars |
| --- | ---: | ---: |
| 1m price | 1 minute | 1 |
| 15m price | 1 aligned quarter-hour | 15 |
| 1h price | 1 aligned hour | 60 |
| Trend 1m | 50 minutes | 50 |
| Trend 15m | 50 complete quarters | 750 |
| Trend 1h | 50 complete hours | 3,000 |

Thus the combined minimum is **3,000 minute constituents forming 50 complete
hourly buckets**, not an arbitrary 3,000-row file. Leading partial buckets, partial
holiday hours and missing minutes can increase the required row count. Structure
and FVG require three 1m candles; liquidity requires four. Recommend 60 complete
hours (3,600 constituents), plus boundary/partial-bucket padding, without changing
any indicator period. Certifier reports actual production aggregation counts and
readiness for each trend. Repository availability and DEC26 liquidity are unproven
until capture; insufficient depth is reported, never replaced with another contract.

## Exact handoff design — offline only

Keep three distinct boundaries: immutable bootstrap final CLOSE label, the new
adapter's startup byte cursor/QPC start, and the first fully observed eligible live
CLOSE label. Archive seeding changes neither receipt clocks nor canonical sequence,
startup cursor, liveness, adapter delivered count or session continuity.

Fresh matched overlap is compared on every OHLCV field and explicitly counted as
skipped, never admitted twice. Conflicting or unrepresented overlap rejects.
The first new completed candle must follow the bootstrap cutoff exactly, or cross
only a bounded EXPECTED_SESSION_GAP proven by the native historical calendar.
The latter join records both close labels and its classification. Subsequent live
continuity rules are unchanged: historical gap proof cannot forgive missing live
observations after handoff. HTF values retain CERTIFIED_BOOTSTRAP until a new
complete live bucket advances their value; current authority stays unknown.

**Operational limitation:** an offline snapshot captured before a later adapter
startup may leave open-market minutes missing before the first eligible live bar.
The current constructor-only bootstrap contract cannot repair that gap. A future
controlled activation needs a reviewed, continuous snapshot/live acquisition
boundary (or additional certified bridge evidence and a separately reviewed
integration). This phase tests the exact-join contract; it does not claim arbitrary
cold-start snapshots can be deployed successfully. Never extend gap allowances,
replay old rows as LIVE or inject history into the existing runtime to bypass this.

## Operator gate and exact capture procedure

Required next actions are manual. No watcher, activation deadline or capture was
started. The production exporter needs no modification or recompile. The **new**
historical component does require installation/compilation in NinjaTrader.

1. Review the certificate/source and preserve the currently running production
   chart and services. Arrange the separate component's installation so compilation
   or chart lifecycle effects cannot interrupt that production instance. If this
   cannot be ensured, defer capture to an approved maintenance window.
2. In NinjaScript Editor create a separate indicator named
   `ArmsHistoricalBootstrapV1`; use the authored source at
   `integrations/ninjatrader/ArmsHistoricalBootstrapV1.cs`, retain NinjaTrader's
   generated wrapper, and compile manually. Do not edit ArmsReadOnlyMarketV1.
3. Create a new empty private output directory with a fresh UUID, outside the live
   inbox. For example, manually run from the repository:

   ```powershell
   $captureId = [guid]::NewGuid().ToString()
   $captureDirectory = Join-Path 'C:\Development\ARMS-AI\.arms-dev\historical-bootstrap' $captureId
   New-Item -ItemType Directory -Path $captureDirectory
   $captureDirectory
   ```

4. Use an isolated diagnostic chart with NQ DEC26 / Minute 1 / CME US Index Futures
   ETH and already-configured UTC. Add exactly one historical component. Set
   **Fresh private output directory** to the printed directory, **From UTC date**
   to `2026-09-14`, **Through UTC date** to `2026-09-21` for this session, and
   **Capture enabled** to true. No provider enum field exists on this component;
   local repository attribution intentionally remains unproven. Do not change
   connections, global merge settings, current live chart, or request history reload.
5. Expect one UUID `.historical.jsonl` and matching `.historical.jsonl.done.json` plus
   the fixed `ARMS_HISTORICAL_BOOTSTRAP_COMPLETE_HISTORY_ONLY` message. Duration has
   not been measured natively; allow approximately two minutes as a planning window,
   not a success guarantee or automatic timeout. On failure/no seal, stop this
   separate capture attempt and report the fixed diagnostic; no provider fallback.
6. Remove only the separate historical component after completion. Preserve the raw
   file and seal unchanged. Request offline review/certification. The available
   certifier command is shown below; substitute the actual matching dataset UUID
   and an unused output filename. It starts no services and does not activate data.

   ```powershell
   python -B -m tools.certify_native_history_v1 `
     --history '<capture-directory>\<dataset-uuid>.historical.jsonl' `
     --seal '<capture-directory>\<dataset-uuid>.historical.jsonl.done.json' `
     --template 'C:\Users\Thecrazyboss\OneDrive\Documents\NinjaTrader 8\templates\TradingHours\CME US Index Futures ETH.xml' `
     --exporter-source 'C:\Development\ARMS-AI\integrations\ninjatrader\ArmsHistoricalBootstrapV1.cs' `
     --output '<unused-private-output>\bootstrap.json'
   ```

7. Independently review the printed hash, provenance, actual bucket counts, gap
   report and cutoff. Capture/certification alone is not controlled-handoff or
   deployment authorization. Leave the existing Sprint 15Y runtime unchanged.

## Verification

The certificate records exact test modules and results. Synthetic native-shaped
fixtures cover sufficient/insufficient depth, duplicate/order/price/volume/identity
faults, daily/weekend/holiday/DST gaps, partial buckets, overlap, expected and
unexpected joins, restart with no receipts, and source pinning. SDK compilation
and reflection-only Cbi inspection passed. Account/execution-construction traps
protect the new Python tests; runtime read endpoints independently confirm disabled
authority. Existing safety/regression suites and frontend projection tests passed.

SDK reproduction (offline only): use .NET Framework64 v4.0.30319 csc with `/target:library`,
references to installed NinjaTrader.Core.dll and NinjaTrader.Gui.dll,
System.ComponentModel.DataAnnotations.dll, System.Web.Extensions.dll, System.Core.dll
and Framework64 v4.0.30319 WPF/WindowsBase.dll; compile the authored source plus
`namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.NinjaScript.IndicatorBase {} }`.
Place outputs in an isolated private directory. Do not install/run the result.

No local commit or push is authorized/performed in this phase. The exact proposed
scope is recorded in `backend/tests/native_historical_bootstrap_sprint16a.json`.
