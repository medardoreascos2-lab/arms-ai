# Sprint 15 — LOCAL_PAPER on the certified native market path

The opt-in coordinator connects the unchanged Sprint 13 native reader and candle
authority to the existing ARMS PAPER runtime. It does not connect to NinjaTrader
accounts or route orders. Native SIM classification stays UNKNOWN, built-in
Sim101 stays NOT_PROVEN, external SIM execution stays DISABLED and LIVE stays NO.
Production/PAPER/quality thresholds remain 90 / 80.5 / 85.

## Ownership and scope

The frozen native reader retains its isolated, disabled validation service. The
new coordinator receives a CLOSED row only after that reader and its existing
CurrentCandleAuthorityV1 have admitted it. Only one separate operational account
can be enabled. Its `_CurrentRuntimeV1` reuses the existing strategy, risk gate,
TradeLifecycleServiceV2, in-memory PAPER connector, accounting and journal. The
validation account never contributes balances, positions or performance to the
operator view. This composition preserves the source hashes of the prior native
certificate; it does not certify the new consumer by inheritance.

No alternative candle normalization, fill pricing, score calculation or PnL
booking was added. FORMING records cannot execute. Only admitted closed 1m data
feeds the existing complete-bar 15m/1h aggregator. Insufficient history remains
unavailable. Real detectors may return HOLD throughout a soak; there is no forced
trade or parameter optimization.

The explicit local entry flag is necessary but insufficient. Calendar/template
and loaded-native hashes, reviewed source hashes, startup sidecar, transport,
timestamps, canonical continuity, certified news coverage and the existing risk
authorities must permit entry. News is checked at both candle availability and
current receipt time. Missing coverage blocks entries; exact event semantics are
those of the existing certified news authority. No holiday or news events are
invented. Existing positions can still exit on otherwise valid fresh candles
while news blocks entries. A transport/calendar/integrity fault freezes processing
and requires review. It never marks or fills from stale prices.

The existing internal account profile supplies risk limits; it is not a connected
prop account. Limits and signal/quality thresholds are not modified. Native
account access and external broker order calls are zero. Calls to the existing
in-memory PAPER connector are local simulated bookkeeping, counted as local fills.

## Durability and reconciliation

The core runtime writes INFLIGHT before mutation and atomically commits its
event, account snapshot and completed-trade journal. The coordinator additionally
writes an INFLIGHT decision trace before invoking it and completes that trace
afterwards. These are separate transactions deliberately: a crash between them
leaves uncertainty, never an invented successful trace. Existing namespaces are
rejected; there is no automatic restart or replay catch-up.

Each completed canonical decision trace contains its source event ID, decision,
risk results, plan, acceptance and local position ID. Reconciliation checks local
fill/order uniqueness, accepted traces against entries, open/closed identities,
account balance/realized/daily/unrealized/equity, and the durable closed journal.
An inconsistency stops further processing. Failed trace persistence is tested.
Reports distinguish synthetic offline witnesses from NATIVE_CURRENT observations.

At the bounded end, entry intent is disabled, a report is written and the runtime
closes. An open PAPER position is recorded as open; no forced exit or price is
fabricated. Review that namespace before starting another account. Daily close,
weekly close/reopen, holiday and reconnect native certifications remain pending.
The initial launcher therefore requires its complete duration to fit an ordinary
open interval and the reviewed window; it stops if that authority changes.

## Dashboard and transport

The existing `/paper-current` page polls the existing dashboard URL every two
seconds with timeout/error clearing. A dedicated loopback FastAPI host exposes
GET `/health`, `/api/v2/paper/readiness` and `/api/v2/backtesting/dashboard` only.
GET requests do not ingest, enable, execute or write journals. There are no account
discovery, switch or order endpoints. The launcher owns ingestion independently.
The projection names LOCAL_PAPER explicitly and shows market/provider/session/
freshness independently, canonical decision/confidence/reason and risk evidence,
positions/entry/SL/TP/PnL, journal and disabled external authorities. Missing values
remain unavailable. Native/account identifiers and raw exceptions are not exposed.

## Operator preparation and bounded run

No native activation was performed by the implementation tests. Before a native
soak, review the operator risk profile and authoritative news snapshot. Prior
permission for `test_environment` covered certification only; this launcher never
loads it implicitly. A private risk JSON must contain exactly the ten ARMS risk
environment keys listed in `operational_paper_soak_v1.RISK_KEYS`, with string values.
Use an approved unchanged profile; do not weaken thresholds to obtain trades.
Missing news allows blocked observation but cannot produce entries.

The launcher uses the already private reviewed spec and evidence directory. It
creates a UUID run directory below `.arms-dev/sprint15`, snapshots every existing
JSONL filename, accepts exactly one newly created market UUID, and requires its
HELLO timestamp to be after arming. Old files, sidecars and expired attempts cannot
activate it. Run/state/report files are exclusive-create; prior evidence is untouched.
The input directory is `.arms-dev/ninjatrader-current` under the repository, exactly
as bound in the reviewed Sprint 13 procedure. Use its resolved absolute path in
NinjaTrader, not a new guessed directory.

1. Verify the Windows clock remains synchronized. Keep all timestamp tolerances
   unchanged. Verify clean tracked tree/index and the Sprint 15 local commit.
2. In a PowerShell terminal at repository root, run a preflight (no watcher):

   ```powershell
   .\scripts\start_local_paper_sprint15.ps1 -RiskProfile <private-approved-risk.json> -CertifiedNews <private-certified-news.json> -EnableLocalPaper
   ```

3. For the dashboard, set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` in its local
   environment, build if changing a production build, then from `frontend` run
   `npm.cmd run dev -- --hostname 127.0.0.1`. Open `http://localhost:3000/paper-current`.
   Leave this page unavailable until the dedicated PAPER API starts; do not use
   dashboard account controls elsewhere. The API port must be free.
4. Within the reviewed **2026-09-21T00:00:00Z through 2026-09-28T00:00:00Z** window,
   and with at least 7,680 seconds before an ordinary session boundary, repeat the
   launcher command with `-Arm`. Capture is 7,500 seconds; activation allowance is
   180 seconds. Keep the terminal/process running. Independently confirm its PID
   is alive and its fresh `waiting.json` says WAITING_FOR_FRESH_NATIVE_SESSION,
   with a future deadline and no `failure.json`/`report.json`. Only then activate.
5. **WINDOW:** existing NinjaTrader NQ chart. **MENU:** Indicators.
   **FIELD:** configured `ArmsReadOnlyMarketV1`. **VALUE:** exactly one fresh instance,
   Expected provider enum `Provider31`, Private output directory = resolved existing
   evidence directory. Chart: `NQ DEC26`, `Minute / 1`, `CME US Index Futures ETH`,
   application timezone `UTC`. **BUTTON:** OK. No strategy, account or order action.
   Do not recompile or change the exporter. A fresh exporter is necessary solely
   for the fresh-session boundary; never activate it before the watcher is waiting.
6. Confirm `active.json` belongs to that fresh UUID and the page labels LOCAL_PAPER.
   Observe without creating demonstration trades. At completion review `report.json`
   (or fail-closed `failure.json`) and both SQLite namespaces locally. A zero-trade
   run is valid observation, not native proof of a full trade lifecycle. Do not
   replay a failed run or enable external SIM execution.

Native soak prerequisites may still be unmet even when offline tests pass. This
sprint prepares and tests the workflow; only a separately observed fresh run can
establish actual native LOCAL_PAPER behavior. Sim101 authority remains unresolved.
