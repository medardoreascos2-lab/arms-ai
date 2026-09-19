# Sprint 08 PAPER release candidate

## Pre-implementation gap audit

| Area | Baseline | Required for RC / disposition |
|---|---|---|
| Startup / modes / identity | PARTIAL: explicit one-shot paper config; general ASGI has separate account runtime | REQUIRED_FOR_RC: opt-in isolated replay application, explicit mode, config and input identity; default app unchanged |
| V31 ingestion / chronology / HTF | ALREADY_CERTIFIED: reviewed historical contracts, closed bars, exclusions | Reuse unchanged; unreviewed current feeds DEFERRED_POST_MVP |
| Detectors / strategy / controller | ALREADY_CERTIFIED: 90 production, 80.5 research, quality 85 | Preserve outputs and monotonic clock; observe actual evaluations |
| Risk / execution / positions / account / journal | ALREADY_CERTIFIED: Sprint07R singular intrabar authority | Reuse exact composition; no independent simulator or alternate PnL |
| Incremental PAPER service | MISSING: one-shot replay only | REQUIRED_FOR_RC: bounded analytical state, serial input, duplicate protection, controls |
| Durable restart | PARTIAL: general durable execution store does not persist historical cursor/HTF/controller | REQUIRED_FOR_RC: write-before-mutation containment; restart RECOVERY_REQUIRED; full operational reconstruction DEFERRED_POST_MVP |
| API / dashboard | PARTIAL: optional final paper snapshot, generic dashboard has another runtime identity | REQUIRED_FOR_RC: isolated authoritative PAPER endpoints and dedicated view inside existing frontend |
| Websocket | ALREADY_CERTIFIED for general account runtime, not historical paper | Use explicit snapshot polling for RC; new PAPER websocket DEFERRED_POST_MVP |
| Health / readiness | PARTIAL: process health alone | REQUIRED_FOR_RC: execution readiness distinct from health, with reasons |
| Shutdown | PARTIAL: general lifecycle persistence cannot restore historical strategy | REQUIRED_FOR_RC: durable stopped state, no automatic resume |
| E2E / soak / frontend | PARTIAL: Sprint07R one-shot evidence | REQUIRED_FOR_RC: new incremental, crash, negative and parity evidence |

NO LIVE TRADING CERTIFICATION. This release is certified historical replay-driven
PAPER only. V31's reviewed 2022–JUN25 contract/calendar boundary is unchanged.
The 80.5 historical result depends on stronger SHORT performance: LONG -$12,600
C0 versus SHORT +$37,200 C0. Longs remain enabled; this is not optimization.

## Architecture and boundaries

`paper_rc_app_v1` is an explicit opt-in application. It does not mount the general
application's order, broker, account-switch or market webhook routes. The default
ASGI application is unchanged. Its existing websocket carries a different runtime
identity, so the RC page deliberately polls the PAPER snapshot endpoint instead.

`PaperRuntimeV1` validates an immutable independent-contract observation segment
with the existing V31 policy. Each serialized command processes one observation.
Ineligible observations advance the source cursor only. Eligible observations
delegate to the frozen historical position update first, advance closed-bar HTF,
then evaluate the existing strategy with a 50-bar analytical history and monotonic
eligible-candle index. The existing final-bar rule forbids new entries on the last
eligible bar. Strategy analysis never sees the remaining input segment.

All entries pass the existing plan, signal, risk and lifecycle authorities. The
independent executor remains absent. The certified historical intrabar manager
alone resolves SL/TP, with SL first when both are touched. Portfolio, account and
journal consume its single result. The RC layer never computes alternative PnL.
An operator entry block does not disable canonical exits on valid later bars.
No invalid or anomaly price may mark or close a position.

Input duplicate identity includes the complete validated observation. An identical
completed event is a no-op, including concurrent delivery. Conflicting or out-of-order
input latches recovery containment before financial mutation. Staleness is measured
against an explicit **historical replay delivery clock**, using the configured quote
age limit. A paused replay is not a current-market feed; wall-clock freshness or 2026
exchange operation is not certified here.

SQLite WAL with `synchronous=FULL` commits an INFLIGHT event before any account or
strategy mutation. A second transaction atomically commits the checkpoint, completed
event and newly completed canonical journal records. IDs are unique. Checkpoints
have SHA-256 integrity checks. This store is durable evidence, not a second financial
ledger used to calculate account balances. SQLite durability still depends on the
filesystem honoring sync requests; hardware power-loss certification is deferred.

Analytical and diagnostic histories are bounded. Immutable source rows are held once;
event IDs grow linearly with input and canonical ledgers grow with trades. No future
slice or growing analytical replay is introduced. Durable single-bar commits trade
throughput for containment and are not the fast research benchmark path.

## Modes, identity and readiness

- `PRODUCTION_POLICY`: explicitly identified; production confluence remains 90.
- `PAPER_RESEARCH`: the only incremental RC execution mode, with confluence 80.5.
- `HISTORICAL_RESEARCH`: separately identified research mode; this RC application
  does not automatically run or promote historical jobs.

An absent or unknown mode/configuration identity is rejected. Without an isolated
PAPER runtime, readiness is false in every mode. No mode grants live authority.
The immutable paper configuration remains `backend/config/paper_research_sprint07r.json`:
quality 85, EMA 10, SL 30, TP 60, research fees $5/contract/side and two adverse ticks
per side. These are research assumptions, not a broker schedule. Existing account
composition uses the configured funding profile; the certified default is Topstep
150K, 0.5% risk, 4,500 maximum drawdown and no configured daily-loss limit. No limits
are replaced. Account configuration, strategy version, source rows, mode and replay
freshness settings contribute to the published configuration identity/hash.

`GET /health` means PROCESS_HEALTHY only. `GET /api/v2/paper/readiness` reports the
separate `paper_ready` flag and reasons. Enabled, valid authorities, validated market
input, available canonical clock, no emergency/recovery fault and no account block
are required. Readiness is permission to evaluate through the unchanged strategy
and risk gates, **not** a claim that an actionable signal or sufficient HTF evidence
exists. The strategy retains its own warmup/quality rules. Actual 1m/15m/1h history
counts are published; unavailable detector results are null, never invented scores.

## Startup and controlled operation

1. Provision the already-certified native export, observation stream and frozen
   Sprint05 manifest. The loader verifies their declared source and stream hashes.
   No dataset is committed, auto-downloaded or substituted with demo data.
2. Set `ARMS_ADMIN_TOKEN` securely in the local process environment. Do not put it
   in command-line arguments, tracked files, browser URLs or build configuration.
   Configure the existing API risk settings as for the certified baseline.
3. Start from the repository root, explicitly choosing a new isolated PAPER namespace:

   ```powershell
   py -m backend.api.paper_rc_app_v1 --manifest backend/tests/research_v31/sprint05/predeclared_experiment.json --contract JUN22 --config backend/config/paper_research_sprint07r.json --state data/runtime/paper-rc-jun22.sqlite --initialization-policy NEW_ISOLATED_PAPER_ACCOUNT
   ```

   Bind is loopback `127.0.0.1:8000`; start one process, without reload/workers.
   Startup never enables or advances the replay. Existing namespace means recovery
   required even when NEW_ISOLATED_PAPER_ACCOUNT was supplied; it never resets it.
4. Start the existing frontend and visit `/paper-rc`. Use the matching API origin
   (default localhost:8000). The API permits the explicit localhost:3000 dashboard
   origin. The page displays the canonical snapshot and separate recovery/readiness
   status. Credentials remain in browser memory.
5. Authenticated POST commands under `/api/v2/paper/` are `enable`, `disable`,
   `emergency_block`, `step`, and `shutdown`. They use the existing
   `X-ARMS-ADMIN-TOKEN` authorization authority. `step` delivers exactly the next
   pinned historical observation; it accepts no caller-supplied prices or orders.
   An operator replay driver may repeatedly issue this command to run continuously.
   GET requests never start, step, mark, fill or alter accounts.

Emergency block is latched for the namespace and cannot be cleared with `enable`.
Controls serialize with candle processing: they apply after an in-flight event,
not retroactively to a fill already authorized. Invalid delivery or loss of durable
storage latches RECOVERY_REQUIRED. A failure to persist completion cannot be retried
as a fresh execution.

## Shutdown and recovery

Use authenticated `shutdown`, then stop the server. Graceful application shutdown
also disables entries, publishes STOPPED and closes the durable store. It does not
force-close positions or invent an end-of-data trade. Back up the complete SQLite
namespace, including any WAL/SHM sidecars while a process is running; do not copy only
the main file while it is active. Prefer backups after orderly shutdown.

**Every restart of an existing namespace is RECOVERY_REQUIRED.** The RC exposes
the last committed snapshot as `LAST_COMMITTED_NOT_OPERATIONALLY_RESTORED`, including
positions, balances, blocks, journal counts and pending-event uncertainty. It does
not construct a fresh financial account, replay pending fills, or claim strategy,
HTF, cursor or position recovery. Corrupt/missing evidence yields unknown account
state and remains blocked. No enable/reset/resume endpoint can override this.

The operator must preserve and reconcile the stored evidence before deciding on
any separately identified new research account. Creating a different namespace is
an explicit new isolated account, **not** recovery or continuation of the old one.
Automated operational reconciliation/resume, storage retention/compaction, broker
reconciliation, current-contract feeds, multi-account continuous trading and RC
websocket push are deferred. No promise of unattended resumable paper trading is made.

## Observability and acceptance evidence

The snapshot supplies canonical starting/balance/equity/peak/daily/realized/drawdown
state and risk reasons, active positions with quantities, last completed trade,
journal counts, input/HTF clock and config identity. `strategy_evidence` observes
actual detector return values without rerunning or changing them. Decision, plan,
risk evaluation and submission are separate fields. A signal opportunity is not
an acceptance; an accepted entry is not a completed trade. Null indicates that a
stage was not evaluated on that bar. `account.open_risk` remains the existing account
projection; inspect active canonical position quantities for actual open exposure.

`test_paper_runtime_sprint08.py` covers the complete synthetic entry/exit/API path,
duplicate/concurrent input, HOLD, rejection, unchanged risk vetoes, emergency exits,
closed HTF chronology, anomaly exclusion, stale/future/order conflicts, lost authority,
storage failure and real subprocess exits at five recovery boundaries. Synthetic
witnesses are explicitly labeled and never replace the real-data research strategy.

`research_paper_rc_sprint08.py` runs the full JUN22 independent segment against the
frozen conservative-cost Sprint07R ledger. Its new `paper_rc_soak_sprint08.json`
records exact trade/account parity, days, wins/losses, drawdown, risk, journal,
bounded diagnostic/history measurements and restart containment. Frozen research
and source/control exports are hash-checked separately. Final test commands,
counts and preservation evidence are recorded in `paper_rc_certification_sprint08.json`.
