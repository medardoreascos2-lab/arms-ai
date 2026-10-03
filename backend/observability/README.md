# ARMS AI Phase 2 observability

## Observability foundation (R29A)

This package defines structured Phase 2 metrics and events for prop-firm rule evaluation, profile freshness, read-only API operations, notification delivery, and aggregate account analytics. Names are restricted to `arms.phase2.*`, timestamps are timezone-aware, numeric metrics use finite `Decimal` values, and attributes are immutable.

Attributes reject credentials, authorization data, cookies, headers, request/response bodies, URLs, free-form messages and exceptions, personal or tenant identifiers, account identifiers, nested values, binary values, floats, and recognizable secret text. Standard recorders accept only bounded labels and aggregate counts; notification payloads and destinations are never recorded.

`Phase2TelemetrySink` is an adapter interface. The included bounded in-memory sink is local/test-only and writes record tuples atomically. Sink failures return `SINK_UNAVAILABLE` without an exception detail. No exporter, network integration, credential, execution authority, or modification to frozen V8 telemetry is included.
