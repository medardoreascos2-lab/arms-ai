# Premium Closed-Beta Scope

## Purpose

This scope defines the Product foundation intended for closed-beta integration. The beta remains a local and synthetic integration target until production identity, payment, provider, and operational reviews are separately authorized and completed.

## Included

- MEDAR conversation presentation through the existing Product adapter, with evidence, confidence, limitations, and explicit degraded states.
- Daily Intelligence from trusted read-only projections, including provenance and freshness.
- Trading Workspace as a read-only view with no order-entry or broker controls.
- Trading Coach as read-only review and improvement guidance.
- Portfolio Guardian as read-only portfolio health and risk presentation.
- Explicit memory consent and review controls; no implicit durable memory.
- In-app notification center, preferences, acknowledgement, snooze, and dismissal; no external delivery transport.
- NQ and MNQ Product presentation within inherited financial authorization and risk boundaries.
- A Research seam for future evidence-backed integration; no invented research results.
- Membership, entitlement, quota, and billing lifecycle abstractions using local synthetic state only.
- Content-free Product analytics, closed-beta capacity policy, and metadata-only feedback.
- Responsive web shell, installability manifest, accessibility improvements, and truthful recovery states.

## Deferred

- Robotics.
- Full smart-home control.
- Genealogy.
- Kitchen integrations.
- Health and wearable integrations.
- Full video AI.
- LIVE trading and any real-money execution.
- Real payments, charges, checkout, and connected payment providers.
- Production authentication and identity providers.

## Safety boundaries

- Read operations never execute trades, create positions, mutate portfolios, or change account state.
- Rejected, blocked, stale, incomplete, unauthorized, or unknown states produce zero execution side effects.
- PAPER and LIVE remain explicitly separate; this Product scope enables neither.
- Billing is synthetic and cannot charge, attach a payment method, or connect a provider.
- Analytics contains fixed categorical metadata and excludes conversation, memory, financial-position, health, and private-message content.
- Support and admin models are read-only projections. Sensitive content is denied by default.
- Unknown or unavailable providers yield explicit unavailable states without fixture, demo, or cached-data substitution.

## Integration entry criteria

Closed-beta integration may start only after the full P120 regression is green, inherited failures are documented, protected Financial and baseline refs remain unchanged, and the final report records the approved closed-beta status. Production auth, real payments, broker connectivity, PAPER execution, and LIVE execution require separate work and authorization.