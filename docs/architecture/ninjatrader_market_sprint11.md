# Sprint 11: read-only NinjaTrader market boundary

Status: offline implementation; native activation and all external SIM phases
remain unapproved by evidence. Starting HEAD is
`c1f6ce6ec78f305f467594a23628b167b3e1fdb5`. No push.

## Integration audit before implementation

| Classification | Evidence | Decision |
| --- | --- | --- |
| EXISTING | Installed NinjaTrader 8.1.8.2 Core/Gui/Client assemblies and 301 local NinjaScript sources | Read-only inspection, no deployment or account enumeration |
| PARTIAL | `external_market_data_provider_v2.py` quote protocol | No OHLCV/closure/contract sequence; cannot certify bars |
| PARTIAL | Abstract `broker_connector_v2.py` | No concrete NinjaTrader transport or strong SIM account proof |
| MISSING | Repository and installed Custom source search found no ARMS NinjaTrader bridge | Add isolated market-only Indicator and reader |
| UNSAFE for this boundary | `MarketDataHubV2` quote dispatch and same-price deduplication | Can update positions and omit distinct flat bars; do not use for candle ingress |
| UNSAFE as provenance | Historical V31 exports, generic `MarketConnector` simulated flag | Neither proves current feed timestamp or account class |
| REUSABLE | Sprint 10 current candle gate, current PAPER coordinator, canonical closed-bar aggregator | Delegate validation, chronology and accounting; no replacement fill authority |
| REUSABLE | Existing `/paper-current` dashboard | Same read-only snapshot shape; LOCAL PAPER only |
| NOT REUSABLE | Stock installed `@Twitter.cs` HTTP listener | Sharing service, unrelated to market-data admission |

Read-only searches covered adapters, connectors, execution, providers, APIs,
scripts, tools, tests, architecture documents and installed Custom C# sources.
No account list, broker connection, original export or configuration was changed.
The inspected local timezone serialization was empty; this does not certify the
running application's timezone. The current contract and data entitlement remain
unknown. Installed vendor assemblies alone are not activation evidence.

## Transport and trust boundary

`ArmsReadOnlyMarketV1` is a chart Indicator, not a strategy. It creates one UUID
JSONL file under an explicit private local directory with exclusive writer and
read sharing. No socket, HTTP ingress, account API, order API, ATI, credential or
return command channel exists. The generated DLL stays local and ignored; only
the reviewed C# source belongs in Git. Do not use a shared or cloud-synced folder.
Private filesystem ACLs are an operator responsibility; this protocol is not
cryptographic protection against a malicious local user with write permission.

Every frame has exactly `schema`, `session`, `sequence`, `event_time`, `kind`,
`payload`. Schema is `arms.nt.market.v1`, sequence starts at zero and covers every
frame, event_time is aware UTC. HELLO pins provider enum (not personal connection
name), NQ master, exact contract, expiry, .25 tick, 20 point value, 1m timeframe,
template, UTC source timezone, CLOSE label, realtime and read_only booleans.
Only one price-connected futures source is allowed; source switching, playback,
simulated-feed provider names, wrong chart/timezone and ambiguity fail closed.
There is no automatic contract rollover.

Subsequent frames are FORMING, CLOSED, HEARTBEAT or DISCONNECTED. Bar payloads
contain UTC `bar_time` and OHLCV. The native heartbeat is five seconds; the reader
deadline is fifteen seconds, bounded by the existing candle freshness limit.
Heartbeats cannot make stale candle prices ready. DISCONNECTED, missing file,
truncation/replacement, sequence gaps/repetition, new session, time regression,
oversize/invalid JSON and unexpected exceptions latch recovery. A partial line
waits only within the heartbeat deadline. No replay catch-up, automatic restart,
automatic rotation, guessed recovery or duplicate financial application occurs.

The reader never writes the stream. Its ASGI host polls independently of GETs,
binds through a separately launched localhost server, and exposes only GET health,
readiness and dashboard routes. It exposes transport state, contract/expiry,
canonical account/risk/journal snapshots, LOCAL PAPER venue, unavailable external
orders/fills and account class NOT_DISCOVERED. It never labels a local fill as a
NinjaTrader SIM fill. Local entries are disabled before every bar, including when
a mistaken in-process caller enabled the injected service. There is no API enable
route. Use a new isolated service with no other ingestion/control owner.

## Time and candle contract

Current-feed time is independently specified, not inferred from V31 exports.
NinjaTrader minute bars carry closing labels; the first tick of a new bar makes
the previous bar's completion observable. See official
[bar construction](https://ninjatrader.com/support/helpguides/nt8/how_bars_are_built.htm)
and [IsFirstTickOfBar](https://docs.ninjatrader.com/ninjascript/isfirsttickofbar).
The exporter requires NinjaTrader's actual GeneralOptions timezone ID to be UTC
before it labels native Time values as UTC. Operator confirmation and native
observations are still required; compilation does not certify a live feed.

OnEachTick preserves same-price volume. Historical callbacks are excluded; the
first partial realtime bar is skipped. Only `[1]` on a later first tick becomes
CLOSED; `[0]` is explicitly FORMING. Idle intervals never synthesize a close. A
delayed confirming tick can fail freshness and require review. Sprint 10 maps the
close to the prior open minute, validates .25 OHLC ticks, volume, freshness, exact
contract validity and certified calendar, then advances completed 15m/1h bars.
Unknown holiday coverage or unexplained open-session gaps fail closed.

Connection health uses market-data `PriceStatus`, not order-adapter `Status`:
[official connection callback](https://docs.ninjatrader.com/ninjascript/onconnectionstatusupdate).
Neither a heartbeat nor a connected price source proves a simulation account.

## Composition after human confirmation

Do not use test fixtures or an invented calendar for activation. Inject an audited
`CurrentFeedContractV1(provider="NINJATRADER:" + provider_enum, contract=...)` with
UTC/CLOSE, verified template and an explicit validity interval. Inject a current
`CertifiedMarketHoursRuntimeProviderV2` with covered dates and actual special hours.
Use the unchanged `PaperResearchConfigV1.load("backend/config/paper_research_sprint07r.json")`,
existing validated `APISettings`, a trusted UTC wall clock and a fresh private
SQLite path. Then compose:

```python
service = CurrentPaperServiceV1(
    gate=gate, config=config, settings=settings, state_path=private_state_path,
    initialization_policy="NEW_ISOLATED_PAPER_ACCOUNT")
reader = NinjaTraderMarketReaderV1(
    service=service, path=explicit_new_session_file,
    provider=confirmed_provider_enum, expiry=confirmed_expiry)
app = create_ninjatrader_market_app_v1(reader=reader)
# Serve this injected app on 127.0.0.1 only; do not use the general production app.
```

Start the consumer alongside a fresh native session, within fifteen seconds of
HELLO; an old file fails rather than being replayed into the current account.
Keep stream and SQLite evidence private and ignored. No dataset is required or
committed. Calendar/provider configuration is intentionally not fabricated here.

## Human configuration checkpoint

Complete these steps only in an idle workspace with no strategies running. This
sprint has not changed the running NinjaTrader application. Do not expose login
secrets, account names or numbers. Keep account discovery deferred.

| WINDOW | MENU | FIELD | VALUE | BUTTON |
| --- | --- | --- | --- | --- |
| Windows File Explorer | Folder properties > Security / Sharing | Prepared local directory | `C:\Development\ARMS-AI\.arms-dev\ninjatrader-current`; verify private ACL and no sharing/cloud sync | OK |
| NinjaTrader Control Center | Tools > Options > General | Time zone | UTC (Coordinated Universal Time); must resolve to Windows ID `UTC` | OK; restart only when operator confirms safe |
| NinjaTrader Control Center | New > NinjaScript Editor | Explorer > Indicators > right-click New Indicator | Name `ArmsReadOnlyMarketV1` | Generate |
| NinjaScript Editor | New indicator tab | Source | Replace wizard source with the repository `integrations/ninjatrader/ArmsReadOnlyMarketV1.cs`; do not copy another generated wrapper | F5 / Compile |
| NinjaTrader Control Center | Connections | Existing entitled data connection | Exactly one operator-approved futures market-data connection; no Playback or Simulated Data Feed | Select configured connection; enter secrets only in NinjaTrader if needed |
| NinjaTrader Control Center | New > Chart (opens Data Series) | Instrument / Type / Value / Trading hours | Provider-confirmed specific NQ expiry / Minute / 1 / explicitly verified template; no continuous contract or date-based guess | OK |
| Chart | Right-click > Indicators | ArmsReadOnlyMarketV1 > Private output directory | Private directory above | Add |
| Chart Indicators | ARMS read only | Expected provider enum | Exact audited provider enum; if unknown, leave blank for the first attempt only | Apply |
| NinjaTrader Control Center | New > NinjaScript Output | Output | Read only `ARMS_READ_ONLY_PROVIDER_ENUM=...`; the blank-provider attempt intentionally emits no stream | No order action |
| Chart | Indicators | Expected provider enum | Enum shown above; remove/re-add the indicator for a fresh session | OK |

The timezone menu, [indicator workflow](https://ninjatrader.com/support/helpguides/nt8/working_with_indicators.htm)
and [F5 compilation](https://ninjatrader.com/support/helpguides/nt8/compiling.htm)
follow NinjaTrader documentation. Exact display names may vary by installed UI
language; the code verifies internal UTC and provider values. If any native
compile/configuration error occurs, stop activation and report only the generic
ARMS status or compile diagnostic, with personal paths removed.

Resume with the non-secret contract, expiry, template, provider enum and current
calendar coverage evidence. Audit the private HELLO before composing the consumer;
then recreate the indicator for a fresh smoke stream. Observe enough complete
minutes for both HTF boundaries and strategy warm-up. Compare native chart time
and OHLCV to canonical snapshots; record zero duplicate bars, broker calls and
fills. Confirm disconnect/reconnect containment and a bounded soak. Only after
that passes may read-only strong SIM account-type discovery begin. Account name
alone cannot grant authority. External SIM orders, lifecycle/reconciliation and
SIM soak remain separate gated work; none is implemented or claimed here.
