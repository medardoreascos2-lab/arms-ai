# Sprint 13 market-open preparation

Prepared from `7a214a3683580aaf2e777a35dca192112f2cc536`. No native capture
was started. The reviewed interval is September 21 00:00 UTC inclusive to
September 28 00:00 UTC exclusive. The loaded calendar binding remains valid
only for that reviewed ordinary-session specification.

Preflight found a CLI integration defect: the reviewed spec identifies the
native enum as `Provider31`, while the canonical reader requires the internal
provider namespace `NINJATRADER:Provider31`. The harness now maps the already
validated enum to that internal namespace. HELLO, the spec, native exporter,
and reader validation remain unchanged.

The harness also checks required local risk settings before watching for new
files, verifies the directory exists, and requires the entire activation plus
capture interval to fit the reviewed window. For market-open purpose, that
interval must fit before the next scheduled close. No waiting across closed
periods, automatic scheduling, calendar extension or fabricated evidence.

The ignored private plan is `.arms-dev/sprint13-market-open-prepare/arm-plan.json`.
It contains fresh, unused state/report paths, the resolved spec and hashes of
all prior JSONL files. Neither the SQLite state nor capture report exists yet.
The launch-time existing-file snapshot isolates old streams; exactly one new
market session may be selected. An old UUID is never resumed or replayed.

## Launch gates

- Review the scoped repair and restore a clean certified Git baseline before
  actual arming. No commit is created by this preparation request.
- Select an explicitly approved local risk profile. Existing test values are
  used only in synthetic regression runs until approved for this capture.
- Recheck HEAD, clean index/tree, calendar/native hashes and unused paths.
- At an ordinary OPEN time in the reviewed window, allow 180 seconds for
  activation plus 7500 seconds (125 minutes) of observation before close.
- Start the agent-side command recorded in the private plan before requesting
  one fresh exporter instance. Announce that the watcher is active; no earlier
  operator activation is evidence for this run.

## Future operator steps

Before arming, verify UTC in Control Center > Tools > Options > General >
Time zone. Verify the chart's Data Series: Instrument NQ DEC26, Type Minute,
Value 1, Trading hours CME US Index Futures ETH. Do not change the template
definitions. No account or order configuration is involved.

After the agent confirms the watcher is active, open chart Indicators (Ctrl+I),
remove the old ArmsReadOnlyMarketV1 if present, and click OK to dispose it.
Reopen Indicators, select ArmsReadOnlyMarketV1 under Available, click add,
set Expected provider enum to Provider31 and Private output directory to
`C:\Development\ARMS-AI\.arms-dev\ninjatrader-current`, then click OK once.
Complete activation within 180 seconds. Leave that one instance and chart open
until the agent confirms the full 125-minute capture finished. No compilation
or another calendar capture is required.

These menus are documented in NinjaTrader's
[Indicators guide](https://ninjatrader.com/support/helpguides/nt8/working_with_indicators.htm)
and [Data Series guide](https://ninjatrader.com/support/helpGuides/nt8/working_with_price_data.htm).

## Result interpretation

PASS requires verified startup alignment/current source in the sidecar, a
matching HELLO, at least 30 seconds of heartbeats, forming observations, at
least two admitted closed minutes, complete 15m and 1h bars, valid UTC/OHLCV/
freshness/order/sequence, unchanged evidence hashes, and zero execution effects.
No strategy trade, signal or profitability result is required. Raw individual
ticks are not exported by this protocol. STARTING/READY are adjudicated from
the sidecar plus HELLO and the reviewed exporter gate, not invented records.

Missing milestones without an integrity fault stay PENDING/inconclusive.
Insufficient HTF observations are never padded. Duplicate or regressed closes,
stale/future/malformed events, heartbeat timeout, provider/session mismatch,
startup contradiction/revocation, unknown calendar, changed binding or any
execution invariant violation fail closed. Stale/duplicate injection is tested
offline; do not inject artificial events into the native evidence.

External broker calls, native account access, SIM and LIVE authority remain zero
or disabled. The canonical harness may initialize its isolated local PAPER
bookkeeping on the first admitted close, with entries disabled; this is not
access to a NinjaTrader account. Daily/weekly/holiday lifecycle and external
SIM certification remain separate pending work.
