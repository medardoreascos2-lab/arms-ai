# ARMS AI MVP 1.0

Controlled PAPER / certified historical replay release. This semantic release
identity is separate from strategy and frozen research configuration versions.
It is displayed on `/paper-rc`. A single local certification commit is the release
boundary; no Git tag or push is required.

## Requirement audit

Starting commit: `ff12649072d7a2ae3762343b225b8b9a67819d76`, branch
`refactor/backend-architecture`. Initial tracked state and index were clean.
Sprint 08's 16-file commit and certification/soak artifacts were inspected.
The initial classifications below carry forward that certified scope; final
Sprint 09 evidence must pass before this release is certified.

| Requirement | MVP classification | Authority / acceptance |
|---|---|---|
| CORE MARKET/REPLAY PATH | CERTIFIED_MVP_1_0 | Hash-verified independent-contract V31 observations; logical replay clock |
| HTF | CERTIFIED_MVP_1_0 | Complete closed 15m/1h bars; bounded histories; no future data |
| DETECTORS | CERTIFIED_MVP_1_0 | Existing actual market/structure/liquidity/FVG/regime outputs |
| CONFLUENCE | CERTIFIED_MVP_1_0 | Production 90; explicitly isolated research 80.5; no score changes |
| QUALITY | CERTIFIED_MVP_1_0 | Existing threshold 85 |
| CONTROLLER | CERTIFIED_MVP_1_0 | Existing chronological strategy decisions |
| RISK | CERTIFIED_MVP_1_0 | Existing account, sizing, projected exposure and execution vetoes |
| PLAN | CERTIFIED_MVP_1_0 | Existing SL30/TP60 research plan; no plan changes |
| SUBMISSION | CERTIFIED_MVP_1_0 | Explicit acceptance required; rejected submission has no fill |
| PAPER EXECUTION | CERTIFIED_MVP_1_0 | Singular lifecycle entry authority; independent executor absent |
| POSITIONS | CERTIFIED_MVP_1_0 | Canonical intrabar management, SL first on ambiguous bars |
| ACCOUNT STATE | CERTIFIED_MVP_1_0 | Sprint07R canonical realization; 17:00 Chicago trading-day clock |
| JOURNAL | CERTIFIED_MVP_1_0 | Same canonical trade result and durable completion record |
| API | CERTIFIED_MVP_1_0 | Opt-in loopback application; authenticated explicit commands |
| DASHBOARD | CERTIFIED_MVP_1_0 | `/paper-rc` projects the same authority; GET/polling is read-only |
| HEALTH | CERTIFIED_MVP_1_0 | PROCESS_HEALTHY describes only process availability |
| READINESS | CERTIFIED_MVP_1_0 | Separate PAPER_READY with fail-closed authority/input/control gates |
| SAFETY CONTROLS | CERTIFIED_MVP_1_0 | Disable, latched emergency, serialized stop; authorized exit management |
| RECOVERY | CERTIFIED_MVP_1_0 | Durable evidence plus containment; every existing namespace is blocked |
| CONFIGURATION IDENTITY | CERTIFIED_MVP_1_0 | Published mode, immutable policy/input/configuration SHA-256 |
| TESTING | CERTIFIED_MVP_1_0 | Complete backend regression, frontend release checks, process smoke and soak |
| DOCUMENTATION | CERTIFIED_MVP_1_0 | This operator contract and frozen Sprint08 architecture |
| Automatic operational recovery | DEFERRED_POST_MVP | Strategy/HTF/cursor reconstruction and reconciled resume are not implemented |
| Current-market feeds / LIVE / broker certification | DEFERRED_POST_MVP | Separate future authorization and independent certification required |

No fundamental architecture repair is planned. A failed required acceptance gate
is BLOCKING and prevents the final certification commit.

## Scope and limitations

MVP 1.0 is a controlled PAPER/replay trading assistant with certified historical
replay, canonical accounting/risk synchronization, journal and dashboard. It is
not live-trading certified, autonomous broker execution, guaranteed profitable,
automatic recovery from ambiguous external state, or production promotion of
80.5. The reviewed V31 contracts/calendar end at JUN25; a present-day feed is not
within this certification. Input exports/streams remain external provisioned
artifacts, verified by the committed manifest, never substituted with demo data.

The historical candidate showed materially stronger SHORT performance (frozen
C0 direction totals: LONG -$12,600, SHORT +$37,200). LONG behavior remains enabled
research. This release does not select directions, tune thresholds, remove losses
or optimize against the old dataset. Research costs remain $5/contract/side and
two adverse ticks/side. SQLite sync durability assumes the storage device honors
sync requests; hardware power-loss certification is deferred.

## Modes and configuration

- `PRODUCTION_POLICY`: policy identity with confluence 90, quality 85; no
  executable PAPER authority is automatically constructed by this mode.
- `PAPER_RESEARCH`: explicit isolated historical replay account, confluence 80.5,
  quality 85, frozen `backend/config/paper_research_sprint07r.json`.
- `HISTORICAL_RESEARCH`: research identity; does not automatically start a job.

None grants LIVE authority. Existing API risk configuration remains required.
The certified default funding profile is Topstep 150K, risk 0.5%, maximum drawdown
$4,500, existing contract/exposure checks, no configured daily-loss limit. Do not
replace limits to recover desired trade counts. Published effective policy and
configuration hash identify the actual runtime; release marketing does not change
the strategy version. Check mode, configuration and source identity before enabling.

## Clean startup

1. Provision the exact certified exports and streams referenced by
   `backend/tests/research_v31/sprint05/predeclared_experiment.json`. The loader
   validates SHA-256, calendar, contract and chronology; missing files fail startup.
2. Securely set `ARMS_ADMIN_TOKEN` in the backend process environment, plus existing
   API risk settings. Never put credentials in commands, logs or build variables.
3. Select a **new isolated** namespace explicitly. Never reuse or remove an old
   namespace to evade recovery containment. From the repository root:

   ```powershell
   py -m backend.api.paper_rc_app_v1 --manifest backend/tests/research_v31/sprint05/predeclared_experiment.json --contract JUN22 --config backend/config/paper_research_sprint07r.json --state data/runtime/mvp-jun22-new.sqlite --initialization-policy NEW_ISOLATED_PAPER_ACCOUNT
   ```

   Use one process, no reload/workers. Bind is `127.0.0.1:8000`. Do not stop an
   unrelated process occupying that port. Startup neither enables nor advances data.
4. In `frontend`, build and start with the matching public origin:

   ```powershell
   $env:NEXT_PUBLIC_API_URL='http://localhost:8000'
   npm.cmd run build
   npm.cmd run start -- --hostname 127.0.0.1 --port 3000
   ```

   Visit `http://localhost:3000/paper-rc`. The permitted CORS origin is exactly
   `http://localhost:3000`; use that browser hostname. The public origin contains
   no credential. Existing Next build fonts may require internet access.
5. Verify `GET /health` and `GET /api/v2/paper/readiness`. Healthy is not ready.
   The page must initially show BLOCKED with PAPER disabled/no eligible market
   input. Enter the administrative credential in browser memory only, then use
   explicit controls. `step` processes one pinned observation; there is no timer
   executing orders and no arbitrary-price/order input endpoint.

An out-of-session observation can be the first source row: it advances only the
observation cursor and cannot establish readiness. After enable and a valid
eligible bar, readiness can become true. It permits evaluation through strategy
and risk gates, not an actionable signal or an assertion of sufficient HTF warmup.
Staleness uses the explicit replay delivery clock, not current wall-clock time.

## Controls, account and journal

Protected POST commands under `/api/v2/paper/` are `enable`, `disable`,
`emergency_block`, `step`, `shutdown`, using `X-ARMS-ADMIN-TOKEN`. Missing/wrong
authorization cannot mutate state. Emergency is latched for the namespace.
An entry block must not disable canonical exits of already authorized positions
on later eligible bars. Ineligible observations cannot enter, mark or close trades.

The lifecycle owns entry; the historical intrabar authority owns exit and PnL.
Account, portfolio and journal consume that one result. The independent executor
is absent. A decision, accepted entry, and completed trade are distinct events.
The page shows actual balance/equity/daily PnL/drawdown, risk, decision, detectors,
confluence/quality, positions, latest canonical trade and journal totals. Null
means unavailable/not evaluated. Account-reported open risk and active position
quantities remain separate existing projections; do not infer a different ledger.
Repeated dashboard/health/readiness reads never execute, mark or advance replay.

## Normal shutdown and restart

Stop the operator replay driver, issue authenticated `shutdown`, confirm STOPPED
and PAPER_READY=false, then Ctrl+C the backend and frontend servers. The API stop
serializes after any in-flight candle, disables further commands, commits the
checkpoint and closes SQLite. It does not invent a close for an open position.
Repeated shutdown is a no-op. Graceful ASGI shutdown also invokes this path.

Preserve the namespace and its WAL/SHM sidecars while active; prefer backups after
orderly shutdown. No new work is accepted after the stop takes effect. The release
process harness invokes the unchanged CLI, delivers the equivalent SIGINT after
API shutdown through its owned child's stdin, and requires process exit code 0.
It never stops an external service or the external V21 process.
Next 16 intentionally exits 130 for SIGINT or 143 for SIGTERM after graceful
server cleanup. The separate frontend shutdown check verifies that installed
handler and port release; these signal exit codes are not build/test failures.

Every existing namespace restarts as `RECOVERY_REQUIRED`, including flat and
completed-trade states. The API exposes last committed evidence explicitly labeled
`LAST_COMMITTED_NOT_OPERATIONALLY_RESTORED`; pending events indicate uncertainty.
Corrupt evidence stays unknown and blocked. No enable/resume/reset command can
override it. Do not infer broker state, fabricate positions, retry pending fills,
or silently reset balance.

Reconcile and preserve old evidence. The supported control path to a valid runtime
is an explicit, separately identified **new isolated research account** after that
review. This is not recovery/continuation of the old account. Automated operational
reconciliation and resume are deferred; MVP makes no unattended recovery promise.

## Certification commands and evidence

- `py -m pytest backend/tests -q --tb=short`
- `py -m pytest backend/tests/test_mvp_release_sprint09.py -q --tb=short`
- `py -m backend.tests.research_release_sprint09 backend/tests/paper_mvp_process_sprint09.json --browser-pause`
- `py -m backend.tests.research_release_sprint09 frontend-shutdown`
- `py -m backend.tests.research_paper_rc_sprint08 backend/tests/paper_mvp_soak_sprint09.json`
- In frontend: `npm.cmd run lint`, `node --test src/lib/*.test.mjs`, `npm.cmd run build`.

Evidence writers use exclusive creation and cannot overwrite frozen reports.
The real smoke retains the first certified JUN22 SHORT loss (-$630), rather than
selecting a profitable demonstration. It checks HTTP submission, canonical exit,
account/journal, durable state, repeat reads and flat/completed process restart.
Synthetic negative tests are explicitly labeled and are not strategy evidence.
Full soak compares every canonical trade and the final account against Sprint07R.
Final commands/results, browser observations and preservation are recorded in
`backend/tests/paper_mvp_certification_sprint09.json`.

The broad release audit found one pre-existing stale route-inventory row for
`GET /api/v2/backtesting/dashboard`: Sprint07R had added the optional read-only
`paper_research_provider.get_snapshot()` projection. Only that row's AST hash,
closure entry and call evidence were refreshed. Route count, observational
classification, authorization, account scope and ownership policy are unchanged.
The legacy `/api/v2/trades/submit` compatibility route is deliberately absent;
its existing integration test is skipped rather than enabling a new execution API.

## Post-MVP roadmap

Prioritize explicit operational reconstruction and reconciled restart testing.
Then separately certify current-market calendars/feeds, multi-account continuous
operation, storage retention, and PAPER websocket integration if needed. Any
future LIVE/broker capability requires separate authorization, configuration,
risk validation and independent certification. Fresh-data strategy research is
a distinct phase and must preserve the frozen baseline and long-side limitation.
