# Phase 7 final integration review (R97C)

## Final outcome

`RUN_STATE=AUTONOMOUS_PHASE7_COMPLETE`

`COGNITIVE_CORE_STATUS=MEDAR_COGNITIVE_CORE_READY_FOR_MODEL_AND_MEMORY_INTEGRATION`

`PRODUCTION_AUTONOMY=FALSE`

The authorized Phase 7 local implementation and validation roadmap is
complete. MEDAR now has a deterministic, provider-neutral cognitive core with
explicit contracts for requests, routing, planning, agents, tools, memory,
evidence, advice, and domain-specific analysis. The final state authorizes a
future, separately reviewed model and memory integration phase. It grants no
authority to call an external model, persist memory, control an operating
system, create external resources, connect a broker or exchange, submit an
order, or enable PAPER, LIVE, or production operation.

Assessment date: 2026-10-03

Branch: `phase7/medar-cognitive-core`

Reviewed Phase 7 head before this report:
`4d6b984e97bc1145364e41534d0fdd0bc233b2e2`

Phase 7 base:
`da23317cb16fa6f8bd70eccb645edf2bb3f661a4`

## Architecture

The implementation under `backend/medar` is a contract-first, local cognitive
layer. A request is normalized and classified, routed to bounded capabilities,
decomposed into tasks, checked as a dependency graph and execution plan,
assigned to agents, and synthesized from evidence with uncertainty and
advisory boundaries. Replanning is controlled and preserves the request and
authority scope.

Each layer returns immutable typed results. Authority-bearing results reject
attempts to assert execution, external-call, or side-effect authority through
manual construction. Domain analysis stays separate from ARMS execution and
risk ownership.

## Cognitive core

`MedarCognitiveCore` composes the classifier, domain router, task decomposer,
agent orchestrator, optional scoped memory reader, evidence aggregator, and
response synthesizer. Its default runtime is deterministic and local. A
`CognitiveRun` cannot report external model use or real-world action.

End-to-end rehearsal covers supported requests, no-result behavior, memory
visibility, unassigned tasks, evidence synthesis, uncertainty, and
multi-domain routing. Read-only cognition does not create trading, portfolio,
account, journal, protection, or order effects.

## Agents

The initial agent registry provides bounded roles for general reasoning,
finance, research, coding, computer assistance, marketing, business, life
advice, and Rosita. Agent contracts declare supported domains and capability
limits. The orchestrator assigns compatible tasks, reports unassigned work,
and resolves conflicts conservatively without acquiring new authority.

## Model routing

Model provider and capability profile contracts are provider-neutral. The
router selects only from registered profiles, applies privacy and risk policy,
and prefers eligible local profiles. It produces a route decision and cannot
invoke a provider. Remote access remains denied without future explicit
integration and authorization; `external_call_authorized` cannot be minted by
constructing a result object.

## Tool routing

Tool contracts define input and output schemas, risk, confirmation, network,
side-effect, and execution-authority properties. The registry contains a
local deterministic calculator and explicit non-executing seams. Authorization
checks bind request, tenant, user, tool, risk, confirmation, and network
requirements before invocation. Rejected calls produce zero invocation and
zero external side effects, and tool traces preserve the decision.

## Memory interfaces

Memory types distinguish working, episodic, semantic, procedural, preference,
and decision-journal data. Reads enforce tenant, user, domain, and sensitivity
scope. Writes are proposals with provenance and review state; Phase 7 does not
provide or silently select a persistent memory backend. Memory evidence keeps
source and lineage metadata through response synthesis.

## Financial routing

Financial routing uses the canonical Phase 6 instrument registry and keeps
analysis separate from execution. Unknown, ambiguous, malformed, unsupported,
or incomplete instrument requests fail closed. No financial capability can
submit an order, change exposure, update an account, or bypass ARMS risk
authority.

### NQ and MNQ

NQ and MNQ are routed as distinct products. Both use a `0.25` tick size; NQ
uses a `$20` point value and `$5` tick value, while MNQ uses a `$2` point value
and `$0.50` tick value. Tests verify exact product identity and prevent NQ/MNQ
substitution. The resulting support is analytical only.

### Crypto arbitrage seam

The crypto arbitrage seam represents venues, quotes, fees, transfer costs,
latency, freshness, capacity, and net opportunity. Missing or stale inputs and
non-positive net results are rejected. It performs no exchange connection,
fund movement, credential access, or trade execution.

## Marketing and business

Marketing analysis structures audience, offer, channel, evidence, constraints,
and recommendations. Business management structures objectives, metrics,
options, risks, and decisions. Both produce advisory artifacts with
traceability and no external publication, purchase, account mutation, or
workflow execution.

## Life advisory

Decision support compares options, assumptions, evidence, uncertainty, and
reversibility. Advisory boundaries label limitations and escalate medical,
legal, financial, safety, and other high-stakes requests for qualified human
review. Advice cannot claim professional authority or perform an action.

## Rosita seam

Rosita has a dedicated domain contract, evidence labels, and response
boundary. Responses separate supported facts, user-provided context,
inference, uncertainty, and recommendations. The seam does not create personal
records, make high-stakes determinations, or gain authority from a domain
label.

## Computer permissions

Computer permission levels and action proposals model observation,
interaction, sensitive operations, and confirmation requirements. The
sensitive-action gate checks scope and explicit confirmation, while all Phase
7 decisions retain `os_execution_authorized=false`. No unrestricted computer
control, native application action, credential entry, destructive operation,
or external side effect is implemented.

## Observability and privacy

Cognitive and tool traces capture bounded decision metadata, outcomes,
warnings, and durations. Metrics summarize local runs without granting
authority. The privacy audit identifies sensitive fields and applies
redaction-safe summaries so raw secrets and unnecessary personal content are
not copied into traces.

## Security review

R97A reviewed request isolation, tenant and user memory scope, tool
authorization, external model denial, financial and Rosita boundaries,
computer permissions, and high-stakes escalation. The review found that normal
factories were fail closed but several public dataclass constructors could be
used to create authority-bearing values directly. Constructor guards now
reject those states for capabilities, domain routes, model decisions, model
routes, tool contracts, tool results, orchestration results, action proposals,
sensitive-action decisions, and cognitive runs.

The regression test verifies that a blocked or rejected result cannot claim
execution authority, authorize an external model call, report operating system
execution, or report external side effects.

## Tests

R97B produced the following verified regression results before this final
report:

| Scope | Selection | Result |
| --- | --- | --- |
| Phase 2 | 18 relevant modules | **332 passed** |
| Phase 3 and research | 39 modules | **657 passed** |
| Phase 4 | 29 modules | **232 passed** |
| Phase 5 | 25 modules | **139 passed** |
| Phase 6 | 27 modules | **145 passed** |
| Phase 7 | 57 modules | **180 passed** |
| Broad safe regression | Deduplicated union, 195 modules | **1685 passed** |

Every successful group emitted one inherited `StarletteDeprecationWarning`
from the installed FastAPI/Starlette test client. It did not change a result.

Unrestricted `pytest --collect-only backend/tests` was also attempted. Pytest
collected 11,371 tests before stopping with 160 inherited collection errors.
The principal inherited blockers were the intentionally fail-closed missing
`ARMS_MAXIMUM_QUOTE_AGE_SECONDS` environment value, the missing
`ARMS_AI_PRIVATE_PATH_MAP` required for portable private evidence, and legacy
collection or dotted-fixture behavior already present before Phase 7. The safe
phase suites do not bypass those controls, and this report does not claim that
unrestricted legacy collection is green.

## Protected baselines

| Baseline | Local HEAD | Worktree | Result |
| --- | --- | --- | --- |
| Frozen V8 | `ca51ebef489ef4f7e80c25e3a4364138147d8346` | 118 pre-existing changes | **UNCHANGED** |
| Published Phase 2 | `423c3b86694f9c1988819cd51d28fedaadd070b6` | Clean | **UNCHANGED** |
| Published Phase 3 | `3f2876afdd2993a8af82f9643bb9fe4de2d34788` | Clean | **UNCHANGED** |
| Published Phase 4 | `1c562ea01c711ecf8a051910ba406277ff1c2d25` | Clean | **UNCHANGED** |
| Published Phase 5 | `80a1a567112d91d1ffe1059787cbac28def388c3` | Clean | **UNCHANGED** |
| Published Phase 6 | `da23317cb16fa6f8bd70eccb645edf2bb3f661a4` | Clean | **UNCHANGED** |

The frozen V8 manifest SHA-256 remains
`a83a17c0b82310eab33cba579be6ef7b08002491f2f71a98a3fdf72d2c248d74`.

## Remaining blockers

1. No real model provider is integrated. Provider selection, credentials,
   privacy review, budgets, availability, and failure handling require a new
   authorized phase.
2. No persistent memory backend is integrated. Storage selection, encryption,
   retention, deletion, consent, tenant isolation, migration, and recovery
   require independent design and validation.
3. Network research, remote tools, exchanges, brokers, and native computer
   actions remain contracts or stubs with no runtime authority.
4. External staging from Phase 6 still requires operator provisioning and
   validation. No Phase 7 component was deployed.
5. The inherited unrestricted test-collection blockers remain unresolved
   outside Phase 7 scope.
6. Any future high-stakes, PAPER, LIVE, or production behavior requires
   explicit authorization and separate safety validation.

## Authority boundary

`NQ_SUPPORT=ANALYSIS_ONLY`

`MNQ_SUPPORT=ANALYSIS_ONLY`

`CRYPTO_ARBITRAGE_SEAM=READY_NO_EXECUTION`

`MARKETING_SEAM=READY_ADVISORY_ONLY`

`BUSINESS_SEAM=READY_ADVISORY_ONLY`

`LIFE_ADVISOR_SEAM=READY_ADVISORY_ONLY`

`ROSITA_SEAM=READY_BOUNDED`

`COMPUTER_AGENT_SEAM=READY_NO_OS_EXECUTION`

`BROKER_AUTHORITY=FALSE`

`PAPER_AUTHORITY=FALSE`

`LIVE_AUTHORITY=FALSE`

`PRODUCTION_AUTONOMY=FALSE`

`UNRESTRICTED_COMPUTER_CONTROL=FALSE`

`EXTERNAL_MODEL_CALLS_PERFORMED=FALSE`

`PERSISTENT_MEMORY_WRITES_PERFORMED=FALSE`

`PUSH_PERFORMED=FALSE`

`PHASE7_LOCAL_INTEGRATION=PASS`

`PHASE7_ROADMAP_IMPLEMENTATION=COMPLETE`

The production-autonomy readiness state prohibited by the roadmap was not
emitted.
