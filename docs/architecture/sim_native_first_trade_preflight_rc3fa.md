# RC3F-A: admission evidence and read-only first-trade preflight

The prior production financial owner deliberately supplied `admission_not_composed`
(`backend/services/sim_native_financial_runtime_service_v3.py`). RC3F-A replaces
that provider after authenticated configuration verification with
`SimNativeAdmissionRuntimeEvidenceV3`. This makes evidence available to the existing
producer; it does not call the producer, submit a signal, publish a command or
activation, or provide an HTTP admission trigger.

The top-level ASGI financial owner supplies the new GET-only endpoint:
`/api/v3/dashboard/sim-native-first-trade-preflight`. It serializes its read with
the financial owner, verifies canonical runtime evidence, and reads the already
published financial snapshot. It performs no ingestion or reconciliation. It
requires the first-operation `NO_OPERATION` state with zero open/closed positions,
journal entries and pending events. Unavailable or expired observations never
become ready. `READY_FOR_AUTHORIZATION` always retains `NOT_AUTHORIZED`.

## Evidence trust and limits

The strict existing dashboard reader validates both canonical snapshot files,
their exact schema/types/identity, future/stale timestamps (15-second maximum),
flat inventory, connection, physical readiness, paths, reconciliation and disabled
capabilities. The adapter additionally reloads the canonical account and policy,
checks the producer's risk authority, authenticates the signed configuration,
verifies its expiry and canonical paths, and pins its complete content and
generation to startup. Commissioning authority/configuration/runtime identities
must agree. Closed sessions return `NOT_READY_SESSION_CLOSED`.

The producer receives only its binding claims and validated runtime evidence.
`observed_at` preserves the original runtime timestamp string. `runtime_ref` is a
deterministic SHA-256 over validated observations, binding, generation, policy and
risk identity. It is **not authentication**, a signature, an admission, or an
execution capability. Native inventory is independently revalidated at entry.

The existing native heartbeat does not publish `controlledObservationOnly`.
`controlled_observation_only` is explicitly identified as
`CERTIFIED_BOOTSTRAP_INVARIANT`, derived only when configured commissioning is
observed. In the certified, unchanged C# bootstrap, `controlledObservationOnly`
is set to true before configuration and never reassigned. This field is not a
new measurement of native memory. A future native enablement must revise this
contract and its observation scheme deliberately; it cannot reuse this inference
to certify a different deployment.

## Separate RC3F-B gates (audit only; none enabled here)

The native sources below retain their baseline line numbers because RC3F-A does
not modify or deploy C#.

* `ArmsSimNativeSubmitBridgeV2.ControlledV3.cs:39`: bootstrap sets observation-only.
  `ArmsSimNativeSubmitBridgeV2.cs:687` blocks one-shot entry after observation-only
  bootstrap; `ControlledV3.cs:295` independently blocks every controlled mutation.
* `ArmsSimNativeSubmitBridgeV2.cs:23`: compile-time native submit is false; auto
  retry remains false at line 25. `ControlledSimOperationV3.cs:440` rejects entry
  with native submit disabled, before consuming activation or creating an order.
* `ArmsSimNativeSubmitBridgeV2.ControlledV3.cs:218`: entry needs the explicit
  one-shot request, the exact operator token, no prior operation/attempt, no
  emergency flatten request, and quantity one. No token value is exposed here.
* Lines 221–244 require a safe CommandId, the exact command schema, authenticated
  `ControlledAdmissionV3`, matching operation/client/command identities, pinned
  instrument/side, and an activation whose ID, digest and wire match admission.
* `ControlledSnapshot()` at lines 303–315 samples native account inventory under
  account collection locks, preserving configured claims, generation and risk
  version. `ControlledAdmissionV3.Validate` in `ControlledSimOperationV3.cs:207`
  checks Sim101/Simulator, connected state, exact instrument, quantity one,
  runtime generation/risk version, flat position, zero active orders, freshness,
  all seven gate approvals, pricing and risk bounds.
* `ControlledMutationGuard()` at lines 292–301 also requires healthy bootstrap,
  unchanged identity/generation, connected state, operation mutation authority
  and no manual reconciliation fence. Order creation at line 319 invokes it.

RC3F-B therefore needs a separately authorized admission trigger, fresh authentic
command and single-use activation, explicit human authorization, a reviewed native
enablement deployment crossing **both** hard blocks, and all current account,
inventory, risk, news, probability, confluence, market, RR/stop, protection and
recovery gates. A valid command/activation alone cannot create an order now.
This document does not authorize any of those changes or actions.

## Validation scope

Synthetic tests use temporary namespaces and test authority material only. The
dry-run traverses the canonical lifecycle and all gates with Commissioning Policy
V1, produces authenticated admission, and asserts no prepared order, execution,
position, native calls or command/activation files. Negative tests verify evidence
and preflight rejection without financial/artifact mutation. Existing RC3E
exactly-once, native B1/B2/B3, PAPER/account-switch, dashboard and durability suites
remain regression gates. No frontend card or execution controls are added.

## RC3F-A verification evidence

Windows Python 3.14: range run **982 passed**; final source targeted run **78
passed** (61 new evidence/preflight cases and 17 financial-owner cases). The final
targeted run includes the last freshness-at-return and unavailable-schema checks.
Frontend: 49 tests passed; lint and production build passed. The existing
Starlette/httpx deprecation warning remains. No dependency was installed.

Backend runs used `-B -m pytest -q -p no:cacheprovider`, an isolated temporary
LOCALAPPDATA, and the existing process-local regression profile. The admission
dry-run separately uses the exact committed Commissioning Policy V1 (including
30-second quote/signal limits), never the legacy regression profile's 300-second
signal allowance. Exact range modules:

```text
backend/tests/test_sim_native_financial_runtime_service_v3.py
backend/tests/test_sim_native_financial_projection_v3.py
backend/tests/test_sim_native_financial_checkpoint_v3.py
backend/tests/test_sim_native_integration_v3.py
backend/tests/test_sim_native_account_authority_v3.py
backend/tests/test_trade_lifecycle_dashboard_event_publisher_v2.py
backend/tests/test_asgi_runtime_integration_v2.py
backend/tests/test_account_runtime_transition_v2.py
backend/tests/test_account_switch_api_v2.py
backend/tests/test_sim_native_dashboard_reader_v3.py
backend/tests/test_dashboard_read_execution_safety_v2.py
backend/tests/test_dashboard_live_api_v2.py
backend/tests/test_phase1_risk_precedence_v5.py
backend/tests/test_sim_native_financial_diagnostic_v3.py
backend/tests/test_durable_crash_recovery_v2.py
backend/tests/test_execution_state_store_v2.py
backend/tests/test_recovery_consistency_v2.py
backend/tests/test_state_recovery_service_v2.py
backend/tests/test_startup_coordinator_v2.py
backend/tests/test_runtime_lifecycle_manager_v2.py
backend/tests/test_account_switch_safety_v2.py
backend/tests/test_account_switch_safety_containment_v2.py
backend/tests/test_phase1_account_switch_full_containment_v2.py
backend/tests/test_sim_native_admission_runtime_evidence_v3.py
backend/tests/test_first_controlled_trade_preflight_v3.py
backend/tests/test_sim_native_commissioning_policy_v1.py
```

The final targeted run used the two new modules above plus
`backend/tests/test_sim_native_financial_runtime_service_v3.py`.

Production acceptance on 2026-09-27: the identified ARMS backend alone was
restarted once to load this endpoint (PID 21208). Three credential-free GETs
returned `NOT_READY_SESSION_CLOSED`, with fresh flat/zero-order observations,
authenticated unexpired configuration and matching policy/risk identities.
Financial status remained `NO_OPERATION`, with all required counts zero. Hashes
of persisted non-heartbeat, non-lock authority/financial files were identical
before/after GETs. Commands, activations, state and reconciliation directories
remained empty; no failure diagnostic was present. Native submit and auto retry
remained false; no native source/project, authority or configuration was changed.
This is a successful rejection of a closed session, not trade authorization.
