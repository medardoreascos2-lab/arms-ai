# Canonical historical accounting (Sprint 07R)

This is an explicit isolated PAPER research composition. Existing application,
LIVE, legacy `run()` and frozen V31 replay compositions are unchanged.
`HistoricalAccountingV1` requires a fresh production engine and a validated V31
single-contract observation stream. It binds a specialized session before replay.

## Authority and event order

1. V31 eligibility admits one chronological completed candle. Its canonical
   availability time advances the injected account clock. Excluded observations
   never mark, trigger, reset, or enter strategy/HTF context.
2. An existing position is marked/resolved from this candle only. The position
   manager extension selects SL before TP when both levels are touched. There
   is no future scan and no entry-bar retrospective execution.
3. The lifecycle propagates that ONE outcome to its existing portfolio, account,
   history, journal, protections/OCO and PAPER position synchronization paths.
   It does not also compute a close-price outcome.
4. Strategy sees the resulting position state. Intent and planned levels remain
   owned by the unchanged parameterized strategy and trade-plan adapter.
5. Both sizing and lifecycle risk evaluation use current balance, daily realized
   PnL and equity drawdown. Existing RiskManagerV2 and ExecutionRiskGateV1 retain
   approval authority. The current account block is fail-closed.
6. Accepted submission creates one fill through existing PaperExecutionEngineV2.
   The independent BacktestExecutionAdapterV2 is disabled in this composition.

## Prices and costs

The planned entry is the decision-bar close. The executed entry is that price
plus adverse entry slippage (minus for SHORT). SL and TP remain the original
plan levels; slippage does not move them. Eligible subsequent high/low reaches
the stop/target. Stop-first resolves ambiguous OHLC ordering.

The existing historical fill convention is retained: trigger fill is the planned
SL/TP level, including gaps. It does not claim a guaranteed real-world gap fill.
Adverse exit slippage applies to that trigger fill separately. With direction
sign +1 LONG / -1 SHORT, gross PnL is `(exit_fill-entry_fill)*sign*quantity*20`.
Net realized PnL subtracts explicit round-trip fees once on completion. Slippage
is already included in fills and is not subtracted twice. NQ tick size is .25.
Research costs are explicit inputs, not a claimed broker fee schedule.

Projected sizing/stop risk includes adverse entry and stop-exit slippage plus
round-trip fees using the existing risk budget and limits. No policy threshold
is changed. Open marks use the eligible close; fees are booked at completion.

No closing-price exit fallback or force-liquidation occurs at END_OF_DATA.
Open positions remain unresolved, with marked equity separate from realized
PnL and an open journal entry. New segments use fresh compositions; a new
contract price can never close an old position.

## Account and journal

PortfolioManagerV2 owns cumulative position totals. AccountStateManagerV2 owns
balance, equity, daily PnL, peak equity, drawdown and blocks. Its existing contract
uses equity drawdown (peak marked equity minus current equity), not just realized
balance drawdown. Daily realized PnL adds only the change in cumulative realized
PnL. The injected availability clock uses the certified Chicago trading date;
no machine date is used for account reset.

TradeJournalV2 is a projection of the canonical result. Historical entry/exit
timestamps and provenance/configuration/cost/account-after metadata are attached
to the same journal entry. SimulatedTrade output is another projection of that
already-realized result for BacktestEngine statistics, never a second execution
or account writer. PaperBrokerConnectorV2's static account response is NOT an
account ledger; canonical account reporting uses AccountStateManagerV2.

BacktestEngine's existing closed-trade equity curve remains a realized-outcome
statistical projection. It is not the marked account-equity series used for
historical risk. Research reports label account equity drawdown separately from
per-cohort realized-trade drawdowns; they never splice independent segments into
an account curve.

## Feedback certification

The frozen simulator and old close-only lifecycle remain comparison evidence.
Counterfactual strategy evaluation restores the legacy active-position input
and controller state without changing prices, scores or strategy code. Each
different decision must reproduce the legacy decision under those restored
inputs and trace to a canonical close or corrected risk rejection (including
their controller/entry descendants). Any unexplained difference stops research.

The architecture is in-memory historical research, not durable operational
recovery or live brokerage. Frozen V30/V31 artifacts are never rewritten.

## Certified PAPER research and existing dashboard integration

`backend/config/paper_research_sprint07r.json` is a separate explicit research
configuration for boundary 80.5, quality 85, EMA 10, SL 30 and TP 60. Production
ConfluenceEngineV2 remains unchanged at 90. The research wrapper changes only
the instance-local grade classification, exactly matching the frozen V30
experiment; it retains scores, approvals and blocking reasons. Both directions
remain enabled. The configuration selects the most conservative declared cost
case: $5 per contract per side plus two adverse ticks per side. These are
research sensitivities, not an asserted broker fee schedule.

An explicit caller loads `PaperResearchConfigV1`, supplies APISettings and a
validated policy/observation stream to `PaperResearchSessionV1`, then calls
`service.run()` once. Construction does not execute. The service uses the
canonical accounting composition and publishes an atomic snapshot. Pass it as
`create_app(paper_research_provider_v1=service)` to expose `paper_research` in
the existing `/api/v2/backtesting/dashboard` GET. AccountOverviewWidgetV2 can
consume the same service through its existing `get_snapshot()` interface.

The projection includes configuration/provenance identity, canonical time,
balance/equity/daily PnL/drawdown/block state, active simulated positions,
latest decision and canonical trade, journal count and risk vetoes. GET only
copies a published snapshot; it never starts replay, updates marks or submits.
During replay the last published state is labeled RUNNING; on failure it is
labeled FAILED. This is not a continuously streaming account endpoint.

The real JUN22 integration witness exactly matches the predeclared 80.5
highest-cost replay: 31 completed trades and $3,870 net, including per-trade
fills, fees and account-after values. The existing API and widget project that
same result. No execution route, default research activation, live connection
or unrelated UI redesign was added.
