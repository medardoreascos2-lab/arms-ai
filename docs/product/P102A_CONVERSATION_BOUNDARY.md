# P102A Product MEDAR conversation boundary

Status: P102A1-P102A12 complete for a local synthetic test. Production customer authentication and a production MEDAR model provider are not connected. The default ARMS API does not mount the Product MEDAR route.

## Request path

1. The Product UI at `/product/medar` sends a bounded message to the same-origin `/api/product/medar` proxy. The browser does not supply user identity, tenant, entitlement, or session authority.
2. The Next proxy is available only when `PRODUCT_MEDAR_LOCAL_TEST_ENABLED=true` in a nonproduction environment. It accepts only the Product prompt fields, rejects caller identity fields, and forwards only to a configured loopback Product MEDAR URL. The synthetic session ID is server-side configuration.
3. The separate Product MEDAR API mounts only with explicit LOCAL or TEST configuration and a `LocalSyntheticSessionProvider`. It checks the loopback peer, trusted customer session, tenant and role consistency, matching active membership, MEDAR entitlement, runtime readiness, and per-plan usage before constructing an invocation.
4. The Product MEDAR adapter creates a conservative canonical request with tools, web, and memory disabled. The local runtime calls the existing `MedarCognitiveCore` and rejects action execution, external model use, memory results, and tool or memory evidence.
5. The adapter projects the canonical `CognitiveResponse` into the Product response. The UI renders its answer, confidence, evidence, warnings, and explicit degraded status. Trust sections and memory context appear only when supported by response data.

In short: Product UI -> same-origin Product proxy -> Product MEDAR API -> trusted customer session -> Product MEDAR adapter -> canonical MEDAR runtime -> canonical MEDAR response.

## Authority and failure behavior

`LOCAL_TEST_ONLY` sessions use synthetic identifiers, deterministic fixtures, expiry, and revocation. The local header is a lookup key, not an identity assertion. Caller-supplied user, tenant, and session fields fail prompt validation. The active membership and session must independently include `MEDAR_CONVERSATION`.

A denied request returns a degraded response before MEDAR invocation. Expired or revoked sessions, wrong tenant, spoofed identity, missing entitlement, inactive membership, disabled local test, unavailable MEDAR or model, and exceeded usage limits are tested for zero downstream invocation. Degraded responses cannot carry an answer, confidence, action proposal, follow-up suggestion, trust claim, or memory context.

The current UI conversation exists only in browser component state. It has no durable memory write. The memory panel marks preferences, goals, decisions, and project context unavailable when the response lacks verified evidence-linked metadata. The trust panel omits absent explanation sections. Action proposals, when supplied by a response, remain `PROPOSED_ONLY`; the UI cannot execute them.

The legacy `/ai/copilot` endpoint is separate. There is no fallback from the Product MEDAR route to `/ai/copilot` or any other route. Product conversation and read-only views cannot create broker orders, PAPER or LIVE positions, protections, or portfolio/account mutations.

## Local verification and limits

The local preview uses `tools/run_product_medar_local_test.py` with the synthetic provider and deterministic canonical core on loopback. The frontend requires explicit local-test environment settings. No production auth provider, payment processor, broker authority, PAPER authority, or LIVE authority is connected. The deterministic core preview is not evidence of a production model integration. Browser DOM automation and real customer-session recovery remain separate future validation work.
