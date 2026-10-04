# P102A MEDAR conversation integration boundary

Status: P102A1 contract and P102A2 local synthetic customer-session boundary implemented. Product MEDAR remains local test only. No production authentication provider is connected, and the Product route is not registered by the default application.

## Trusted session

`backend.product.customer_session` defines an immutable UTC customer session and a provider-neutral validation and identity-resolution contract. The only implementation is `LocalSyntheticSessionProvider`, which accepts synthetic identifiers, deterministic fixtures, expiring sessions, and revocation. It carries `LOCAL_TEST_ONLY` source and assurance and `SYNTHETIC_FIXTURE` authentication method. It has no passwords, cookie secrets, external network, or customer account creation.

The session provider is the only source for Product MEDAR user, tenant, session, roles, and entitlements. A session ID supplied in the local test header is only a lookup key. Directly constructed or modified session objects are rejected unless they are the current provider-owned instance.

## Product access

`MEDAR_CONVERSATION` is the canonical entitlement. Product MEDAR is `AVAILABLE_LOCAL_TEST` only with a valid trusted local session, matching active membership, entitlement in both session and membership projection, and an injected MEDAR runtime. Other Product surfaces keep their existing decisions. No Product access decision grants admin, broker, PAPER, or LIVE authority.

## Local test API

`create_local_test_product_medar_router` constructs a loopback-only router for explicit local mounting. The default application does not mount it. The route accepts only the bounded Product prompt schema; caller user, tenant, and session fields fail validation. A denied request returns an explicit degraded status before constructing or invoking a MEDAR request. An allowed request passes provider-derived scope in `ProductMedarInvocation` and uses a conservative canonical MEDAR request with web, tool, and memory flags disabled. The legacy `/ai/copilot` route remains separate.

The runtime is injected. No production provider, external auth endpoint, production MEDAR availability, or UI send control is claimed. The P102A3 onward roadmap was not present in this worktree's Product documentation, so further milestones require their specific contract before implementation.
