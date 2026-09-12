# ARMS AI — CODEX OPERATING RULES

## 1. MISSION

ARMS AI is a professional AI-assisted trading and decision-support platform.

Priority order:

1. Safety
2. Correctness
3. Data integrity
4. Risk control
5. Testability
6. Maintainability
7. Performance
8. Development speed

Never sacrifice trading safety, risk controls, or data integrity for convenience or speed.


## 2. WORKING PRINCIPLE

Work autonomously only inside the scope of the approved task.

For every task:

1. Inspect the relevant implementation first.
2. Understand existing architecture before editing.
3. Identify root cause.
4. Make the smallest safe change.
5. Preserve unrelated working behavior.
6. Add or update regression tests.
7. Run relevant tests.
8. Review the final diff.
9. Report exactly what changed and what was verified.

Do not perform unrelated refactors.


## 3. TRADING SAFETY — ABSOLUTE RULE

A blocked, rejected, invalid, incomplete, unsafe, or unauthorized trading signal must NEVER produce an execution side effect.

If a signal is blocked or rejected, it must not:

- prepare an executable order,
- send an order to a broker,
- create a PAPER position,
- create a LIVE position,
- modify portfolio exposure,
- alter account state as if execution occurred,
- create execution records implying a fill,
- create protections or OCO orders,
- bypass news restrictions,
- bypass risk restrictions,
- bypass probability requirements,
- bypass market-state requirements,
- bypass account restrictions.

`accepted: false` means ZERO execution side effects.

Protect this invariant with automated tests.


## 4. RISK MANAGEMENT

Risk controls are fail-closed.

If required risk information is missing, inconsistent, stale, or invalid, do not execute.

Never weaken or bypass:

- daily loss limits,
- maximum drawdown,
- contract limits,
- position sizing,
- exposure limits,
- stop-loss requirements,
- account-specific rules,
- trading-blocked state,
- economic-news restrictions,
- market-data freshness requirements.

Any risk-related modification requires tests.


## 5. PAPER AND LIVE EXECUTION

PAPER and LIVE execution must remain explicitly separated.

Never:

- automatically convert PAPER execution into LIVE execution,
- enable LIVE trading without explicit authorization,
- send real-money orders merely because supporting code exists.

Any future LIVE capability requires explicit configuration, explicit authorization, and independent safety validation.


## 6. READ OPERATIONS MUST NOT TRADE

Read-only operations must never cause trading side effects.

This includes:

- GET endpoints,
- dashboard loading,
- analytics,
- status requests,
- health checks,
- reports,
- widgets,
- WebSocket subscriptions,
- portfolio views.

Displaying or requesting information must never submit or create an order.


## 7. ACCOUNT STATE AND RECOVERY

Account state, broker state, portfolio state, journal state, and risk state must remain consistent.

Changes affecting:

- realized PnL,
- daily PnL,
- balance,
- equity,
- drawdown,
- positions,
- account switching,
- snapshots,
- restart recovery

must be validated for synchronization and recovery behavior.

Never report successful recovery if operational state was not actually reconstructed.


## 8. DATA INTEGRITY

Do not silently substitute hardcoded, simulated, demo, fixture, or placeholder values for real runtime data.

When simulated data is intentionally used, make it explicit.

Backtesting, Walk Forward, Monte Carlo, certification, and performance reports must preserve traceability to the actual dataset and strategy being evaluated.


## 9. TESTING

Every bug fix must include a regression test whenever practical.

Tests must verify behavior and relevant side effects, not only response fields.

For execution-related changes verify, where applicable:

- broker calls,
- PAPER execution,
- positions,
- protections/OCO,
- portfolio state,
- account state,
- journal writes,
- emitted events.

Never claim a task was tested if it was not tested.


## 10. SCOPE CONTROL

Do not modify unrelated files.

Do not perform large architectural rewrites unless explicitly requested.

Do not delete legacy modules merely because they appear unused.

Prefer incremental consolidation over destructive rewrites.


## 11. GIT SAFETY

Before changes, inspect Git state.

Never:

- discard unrelated user changes,
- reset the repository destructively,
- force push,
- rewrite history,
- delete branches,
- remove user work.

Do not commit or push unless explicitly authorized for the current phase.


## 12. SECURITY

Never expose or commit:

- passwords,
- API keys,
- broker credentials,
- tokens,
- private keys,
- personal credentials.

Do not weaken authentication, authorization, validation, or risk controls to make a feature work.


## 13. DEPENDENCIES

Do not add dependencies unless genuinely necessary.

Prefer existing project capabilities and dependencies whenever reasonable.


## 14. DEFINITION OF DONE

A task is complete only when:

1. Requested behavior is implemented.
2. Relevant tests pass.
3. No known critical regression was introduced.
4. ARMS AI safety rules remain protected.
5. Final diff is reviewed.
6. Remaining limitations are reported.

Never claim LIVE functionality when only PAPER/simulated behavior was verified.


## 15. COMPLETION REPORT

At the end of every development phase provide:

### COMPLETED
What was implemented or fixed.

### ROOT CAUSE
The verified cause of the issue.

### FILES CHANGED
Exact files modified.

### TESTS EXECUTED
Exact tests run.

### TEST RESULTS
Pass/fail results.

### SAFETY INVARIANTS VERIFIED
Relevant execution/risk guarantees checked.

### DIFF SUMMARY
Concise explanation of the resulting diff.

### REMAINING ISSUES
Anything incomplete, uncertain, or blocked.

### NEXT RECOMMENDED STEP
One highest-priority next action.


## 16. AUTONOMY POLICY

Codex may autonomously:

- inspect repository files,
- analyze architecture,
- edit files required by the approved task,
- create appropriate tests,
- run relevant local tests,
- fix failures directly caused by its own changes,
- review its own diff.

Codex must stop and request approval before:

- changing fundamental trading architecture,
- enabling LIVE trading,
- connecting or modifying real broker execution,
- weakening risk or safety controls,
- deleting substantial functionality,
- destructive Git operations,
- changing secrets or credentials,
- materially expanding task scope.

Autonomy is encouraged inside a clearly defined phase.

Autonomy does not mean unlimited scope.


## 17. ARMS AI CORE PRINCIPLE

ARMS AI must become safer as its autonomy increases.

No autonomous feature may bypass:

- risk management,
- execution safeguards,
- account protections,
- testing requirements,
- human authorization boundaries.

Reliability and controlled execution take precedence over convenience or speed.
