# RC3E-R1 native financial ownership

The top-level production ASGI lifespan constructs one
`SimNativeFinancialRuntimeServiceV3`. It starts before the PAPER coordinator,
stops after it, and is never rebuilt by a PAPER account switch. Child applications
receive only a read function through the separate financial GET router. Explicit
injected standalone PAPER contexts retain their existing test/containment contract.

Startup reads the existing CurrentUser authority, authenticated V3 configuration,
canonical native binding, and Commissioning Policy V1. It verifies exact identity,
risk version, configuration generation/expiry, and canonical path pins before
starting the financial checkpoint. Invalid configuration leaves PAPER usable and
native observations unavailable. Configuration is reverified on every observation;
expiry also invalidates cached GET responses. Nothing provisions or renews authority.

Financial checkpoints use `LOCALAPPDATA/ARMS-AI/sim-native-v3/runtime/financial`,
separate from the signed native state path. The existing runtime, checkpoint,
portfolio, journal, command spool, integration, and event publisher are reused.
The service never calls `submit_signal` or `publish_admitted`. Its admission
evidence provider always raises `SIM_NATIVE_ADMISSION_NOT_COMPOSED`.

The worker observes every protection timeout / 4 (2.5 seconds for V1). Before
ingestion it authenticates the complete visible phase sequence and rejects gaps,
identity changes, contradictory executions, or redirected paths. It then invokes
the existing integration's financial reconciliation and receipt publication. A
failure latches native availability off until explicit restart. No GET reconciles,
writes a receipt, or performs a broker operation. Empty verified durable financial
state is `NO_OPERATION`; unavailable ownership is never represented as zero trades.

`publish_pending()` remains at-least-once transport with stable event IDs. The
dedicated projection consumer validates events against committed native facts and
atomically replaces a fsynced document containing presentation event records and
processed IDs together. Retry after replacement is a successful no-op. Generic
DashboardEventBusV2 is unchanged. Producer acknowledgment occurs only after the
consumer succeeds. Startup can reconstruct a missing projection from canonical
events, including already acknowledged ones; malformed projections fail closed.

The financial endpoint publishes canonical checkpoint facts plus durable projection
IDs/counts, never PAPER financial data. Unrealized PnL is the checkpoint value,
not a live market valuation. The browser has a separate observation-only card and
ages the response using the service-provided observation budget. No signal,
admission, arm, activation, submit, cancel, or flatten route is introduced.

Certification uses temporary authenticated configuration and the existing synthetic
SDK harness only. This implementation does not start/restart the deployed backend,
write live native artifacts, or enable an initial controlled trade. Production
startup/browser verification and a separate admission-authority phase remain gates.
