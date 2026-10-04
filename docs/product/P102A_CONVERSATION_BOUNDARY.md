# P102A MEDAR conversation integration boundary

Status: P102A1 contract committed; P102A2 blocked by the explicit production-auth-provider stop condition. No Product MEDAR route or conversation send control is exposed.

## Approved boundary

The Product MEDAR API is a separate authenticated adapter over canonical `backend.medar.request.CognitiveRequest` and `backend.medar.response.CognitiveResponse`. It must bind user, tenant, and session from a trusted server authentication context, check current membership and MEDAR entitlement, then invoke MEDAR only after authorization. The legacy `/ai/copilot` endpoint calls a separate conversation engine and is not a Product MEDAR fallback.

`backend.api.schemas.product_medar` now defines a bounded caller prompt and a response projection. The prompt rejects caller-supplied `user_id`, `tenant_id`, and `session_id`. The response carries status, answer, confidence, user-facing reasoning summary, sources, tool and memory evidence, warnings, follow-up state, and proposals. Proposals remain `PROPOSED_ONLY` with `execution_authorized=False`. Degraded responses cannot claim a synthetic answer, confidence, or proposal. The contract does not authenticate requests or invoke MEDAR by itself.

## Blocker at P102A2

There is no production customer HTTP authentication provider in `backend/api` that verifies an unexpired session and supplies a trusted user, tenant, and session. `backend.phase4.transport_authorization.AuthenticatedUserTransportPrincipal` is a read-authorization contract, not an HTTP credential resolver; it has no session identifier or session expiration. `backend.medar.trusted_runtime_identity.LocalAdminIdentityAuthority` explicitly does not provide per-user authentication and cannot stand in for a customer session. The existing API dependency authenticates administrative operations, not Product users.

The canonical Product access projection also leaves `ProductSurface.MEDAR` in `SURFACE_NOT_READY`, so no current membership grants the needed MEDAR entitlement. Granting visibility based only on a tier would bypass the requested entitlement check.

The user brief explicitly requires stopping when a production auth provider is required. P102A2 through P102A10 and P102B onward remain pending. Resume only when a trusted customer session provider and canonical MEDAR entitlement are available or separately authorized for implementation. Until then, denied and unavailable states remain explicit and cause zero MEDAR invocation, tool execution, memory writes, or broker/PAPER/LIVE effects.
