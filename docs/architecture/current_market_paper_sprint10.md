# Sprint 10: current-market PAPER boundary

Baseline: a75fbaf7ccd7698b341930d8c409ba8d792ad2cf. No LIVE authority.

## Architecture audit before implementation

| Component | Status | Decision |
| --- | --- | --- |
| ExternalMarketDataProviderV2 | PARTIAL | Quote boundary only; lacks contract, close notification, volume and sequence. Never infer a closed bar from it. |
| DataFeed / MarketConnector | BLOCKING | Legacy mutable quote holder / explicitly simulated connection; neither proves external current data. |
| MarketDataHubV2 | PARTIAL | Price routing can reach position updates; same-price duplicate suppression is unsuitable for flat closed bars. Do not route current candle admission through this authority. |
| CandleManager | PARTIAL | Bounded storage, no closure/identity/ordering guarantees. |
| ClosedBarAggregatorV1 | EXISTING_AND_REUSABLE | Sole complete-bucket 15m/1h aggregation; aware input, preserved gaps, no interpolation. |
| MarketHoursServiceV2 and certified runtime provider | EXISTING_AND_REUSABLE | Fail closed on uncertified dates; reuse Chicago session/trading-day authority. Provider/calendar identity and coverage must be explicitly supplied. |
| HistoricalEligibilityV31 | DEFERRED for current ingestion | Frozen 2022–2025/native UTC-end contract; never assume these source semantics for another feed. |
| HistoricalAccountingV1 | EXISTING_AND_REUSABLE | Frozen canonical PAPER entry, intrabar stop-before-target exit, costs, account, portfolio, journal and synchronized risk. Its finite row cursor is specialized only in the new current subclass; the historical source remains byte-identical. |
| PaperRuntimeV1 | PARTIAL | Durable event/uncertainty containment and read projections are reusable; finite replay clock/cursor/last-bar rules are not current-feed rules. |
| PAPER broker/lifecycle | EXISTING_AND_REUSABLE | Exact existing simulated composition only; no broker adapter replacement or LIVE mode. |
| Current canonical closed-1m authority | MISSING | Add one provider-neutral gate before strategy/account mutation. |
| Provider adapter / current contract selection | BLOCKING for external smoke | No audited configured closed-bar adapter found. Explicit instrument/contract configuration; no automatic rollover or historical fallback. |
| Dashboard polling | EXISTING_AND_REUSABLE | Detached authoritative snapshots and explicit authenticated controls. |
| General WebSocket hub | DEFERRED | Existing broadcast hub lacks this isolated PAPER runtime's version/reconnect contract; retain polling rather than attach an unrelated authority. |

## Chosen contract

The provider must explicitly distinguish RAW_EVENT, FORMING_CANDLE and
CLOSED_CANONICAL_CANDLE. Only the last category may enter the strategy. Source
bar labels explicitly declare OPEN or CLOSE semantics; both are offset-aware.
Event and receive times are separate. Canonical labels are Chicago open times,
compared as UTC instants. A close notification cannot precede minute completion.
No local-time guessing, synthetic candles, interpolation or automatic rollover.

Instrument identity is explicit NQ contract, tick size 0.25, point value 20,
trading-hours template identity, provider identity and timestamp contract.
Provider events carry a contiguous sequence and event identity. Old/conflicting
events never amend previously analyzed bars. Duplicate payloads are no-ops;
duplicates never refresh freshness. In-memory duplicate history is bounded;
an older unprovable replay fails closed instead of risking re-execution.

Current PAPER uses only received closed bars. Entries occur at their closes;
only subsequent admitted bars may resolve SL/TP using the existing canonical
intrabar authority and configured costs. No future sequence is preloaded.
Forming/raw observations cannot mark or execute positions.

Disconnect/stale data blocks new entries and supplies no invented exit price.
Reconnect requires a contiguous provider sequence and no missing open-market
minute before execution can resume. Unproven continuity enters latched
RECOVERY_REQUIRED; restart remains evidence recovery, never automatic operational
resume. Expected certified closed-session gaps may be preserved; missing open
minutes cannot be silently bridged. Account authority never changes on reconnect.

Provider smoke remains unavailable until an operator supplies an audited source
adapter, explicit contract and certified current calendar. Offline fixtures are
always labeled as fixtures. Certification of this boundary is not certification
of an external feed or LIVE trading.

## Implementation and operation

`CurrentPaperServiceV1` serializes a `CurrentCandleAuthorityV1` and a private
streaming specialization of `PaperRuntimeV1`. Narrow replay extension
points select the accounting/session class and finite-input boundaries.
Their historical defaults are unchanged. The current accounting subclass
validates/advances one admitted observation and delegates trading-day rollover
to the existing account manager; the frozen historical accounting source is
not edited. The current
path can decide on the latest closed candle without preloading a future candle;
an open position remains open until a subsequent valid close resolves its range.

An operator must supply the `CurrentFeedContractV1`, a
`CertifiedMarketHoursRuntimeProviderV2` with explicit coverage/special hours,
the existing certified `PaperResearchConfigV1`, explicit `APISettings`, a fresh
private SQLite namespace and `NEW_ISOLATED_PAPER_ACCOUNT`. Use an aware actual
UTC clock for external operation; injected clocks and `fixture=True` identify
the deterministic test harness. No current contract or calendar is selected by
default. A changed/expired contract requires a separately reconciled namespace.

The provider adapter calls `service.connection(True)` after its subscription
is established and passes each explicitly typed `CurrentMarketEventV1` to
`service.ingest(event)`. Receive time is captured by the trusted adapter, not
the dashboard. The sequence must be contiguous across all three event kinds;
an adapter that cannot prove that contract is not suitable. A transport outage
calls `connection(False)`. There is no unauthenticated data-ingestion endpoint.

The first admitted closed candle initializes a disabled PAPER account. An
explicit administrative enable command is then required. Instantiate
`create_current_paper_app_v1(service=service, admin_token=...)` using the existing
secret configuration channel (never command-line credentials). The API exposes
the existing health/readiness/dashboard read paths and authenticated
enable/disable/emergency-block/shutdown commands. Replay `step` is unavailable.
The `/paper-current` frontend is a read-only two-second polling monitor. Its
values come from the canonical snapshot; errors and five-second request timeouts
clear the displayed snapshot. Completed canonical journal evidence is explicitly
labeled `SIMULATED / PAPER` with its current provider and closed-bar clock.
The existing `/paper-rc` page remains the certified historical replay interface.

Existing SQLite namespaces always expose reconciliation evidence with
`RECOVERY_REQUIRED`, regardless of a new provider connection. They never rebuild
an empty account over an existing ledger. Emergency stop and feed integrity
faults have no reset endpoint. A disable/emergency entry veto leaves canonical
position exits active on subsequently admitted valid closed bars. An unproven
gap supplies no exit price and requires reconciliation.

Snapshot hashes bind the explicit feed/calendar, the starting observation and
the unchanged PAPER/account/risk configuration. `source_sha256` on a current
observation is the typed event fingerprint, not a claim that a historical export
file exists. `raw_row` is that fingerprint for compatibility with the existing
evidence identity interface; no raw export is invented. Receive timestamps are
excluded only from retransmission identity, never from freshness validation.

The feed duplicate cache holds at most 2,048 events, each analysis/HTF history at
most 50 bars, and accounting retains one initial row plus one pending/current
observation. Diagnostic histories are cleared by the existing runtime. Durable
event evidence grows with received closed bars; canonical trade/journal ledgers
grow with accepted trades. This sprint does not truncate authoritative ledgers
or claim constant memory for an unlimited lifetime of trades.

## Offline certification scope

`backend/tests/test_current_paper_sprint10.py` contains explicit synthetic
fixtures, not production market data. It covers validation, flat bars, forming
bars, DST offsets, close labels, stale/disconnected conditions, calendar and
special-hours vetoes, sequence gaps, duplicates/concurrency, risk and submission
rejection, canonical wins/losses, read safety and restart containment. Independent
canonical candle construction proves HTF equivalence; actual detector outputs
are compared against historical replay on the same closed sequence.

The soak streams 3,000 closed minutes over multiple Chicago trading days,
including certified daily maintenance gaps, retransmissions and five
disconnect/reconnect events. Two distinct synthetic plans deliberately exercise
a win and a loss, not profitability. The existing lifecycle's 30-second
identical-plan retry suppression remains intact. No fixture changes a strategy
threshold, detector score, execution cost, risk limit or SL/TP rule.

External-provider smoke is deferred because no audited configured closed-bar
source was found. The next integration must demonstrate native close semantics,
contract/calendar coverage, sequence continuity and a trusted wall clock before
activating this PAPER path. The polling path is certified here; WebSocket
publication remains explicitly deferred.
