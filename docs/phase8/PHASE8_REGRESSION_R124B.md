# Phase 8 R124B Regression Evidence

Date: 2026-10-04
Branch: `phase8/medar-model-memory-learning`
Phase 8 hardening HEAD tested: `4bcf68a038833d15dd4f6047462c9bca119a833c`

## Complete Phase Regression

The test runner discovered every `backend/tests/test_phase{2..8}*.py` module at runtime and executed the resulting set in one pytest session.

- Phase 2 modules: 5
- Phase 3 modules: 16
- Phase 4 modules: 29
- Phase 5 modules: 25
- Phase 6 modules: 27
- Phase 7 modules: 58
- Phase 8 modules: 87
- Result: **1466 passed**
- Warning: 1 inherited `StarletteDeprecationWarning` from the installed FastAPI test client
- Duration: 98.87 seconds

No Phase 8 test failure or dependent Phase 2 through Phase 7 regression was observed.

## Broader Safe Regression

A second suite selected non-Phase modules whose filenames contain safety, security, authority, privacy, risk, recovery, read-only, or zero-side-effect markers. Modules that directly bootstrap the API application were excluded because required runtime configuration is intentionally absent in this local Phase 8 environment.

- Executable modules: 93
- Result: **1124 passed**
- Warning: 1 inherited `StarletteDeprecationWarning`
- Duration: 71.37 seconds

This broader run included execution safety, authority, recovery, and risk tests outside the Phase 2 through Phase 8 named suites. No Phase 8 change was implicated in a failure.

## Inherited Configuration Blockers

Whole-backend collection was attempted without supplying production-style runtime configuration.

- Tests discovered before interruption: 11,834
- Collection errors: 160
- Representative fail-closed error: required `ARMS_MAXIMUM_QUOTE_AGE_SECONDS` was unset

The following six otherwise selected broad-safety modules were separately confirmed as blocked by the same missing runtime configuration path or by importing another blocked API bootstrap test:

1. `test_certified_current_paper_authority_factory_v1.py`
2. `test_phase1_risk_precedence_v5.py`
3. `test_maximum_open_positions_policy_authority_v2.py`
4. `test_paper_execution_fill_policy_authority_v2.py`
5. `test_paper_execution_slippage_policy_authority_v2.py`
6. `test_sim_native_account_authority_v3.py`

A diagnostic run that included four executable-but-config-dependent modules produced 1,167 passes, 39 failures, and 25 setup errors. The failures and errors were caused by absent required API settings. Phase 8 did not modify the configuration modules or these tests.

The required settings were not synthesized because doing so would weaken the meaning of the repository's fail-closed startup contract and would exceed Phase 8 scope.

## Safety Boundaries Confirmed

- Rejected or blocked signals retain zero execution side effects in the green dependent suites.
- Phase 8 model and memory runtime has no broker, PAPER, LIVE, production autonomy, or external-call authority.
- Memory reads remain bound to authority-issued tenant and owner identity.
- Sensitive Phase 8 durable journal and lesson fixtures remain AES-256-GCM encrypted with ephemeral local-development keys.
- Memory injection is blocked before model invocation.
- Model output cannot grant tool, execution, routing, deployment, memory mutation, broker, PAPER, LIVE, or computer authority.
- Learning proposals cannot automatically apply or deploy changes.

## Scope Statement

This evidence validates local Phase 8 foundations and their tested dependencies. It does not claim real local-model quality, production key custody, broker connectivity, PAPER authority, LIVE authority, production deployment readiness, or unrestricted autonomy.
