# P104 Product customer financial access boundary

Status: local synthetic read-only foundation complete. Published Financial
Intelligence integration remains INTEGRATION_PENDING.

## Current request path

Product financial GET API -> trusted Product customer session -> active membership
and Product financial entitlement -> server-issued customer financial scope ->
Product read-only provider -> Product projection with provenance and freshness.

The local provider is enabled only by explicit LOCAL or TEST configuration. Its NQ,
MNQ, portfolio, coach, shadow MEDAR, alert, and daily samples are labeled
SYNTHETIC, LOCAL_TEST_ONLY, and NOT_REAL_ACCOUNT_DATA.

## Future integration seam

The intended future path is:

Product Financial API -> Product Read-Only Provider -> Financial Intelligence public
API/contracts.

The Product adapter may consume stable published response contracts and map them into
the Product projection models. It must not import Financial Track implementation
modules, copy Financial algorithms, infer missing values, or add write operations.
Until those public contracts and their mapping specification are available, the
adapter returns INTEGRATION_PENDING.

## Authority

The boundary has no endpoints or methods for order placement, cancellation, position
changes, portfolio modification, rebalancing, deposits, withdrawals, broker
connection, PAPER enablement, or LIVE enablement. Caller identity and account or
portfolio references never override the trusted server-side scope.
