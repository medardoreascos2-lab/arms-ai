# Product surface contract

`resolve_product_access` consumes the server-side membership entitlement projection. It recognizes FREE, PRO, PREMIUM, ELITE, and ADMIN plan IDs without embedding pricing. An ADMIN product plan also requires the existing TENANT_ADMIN role, but never becomes canonical administration authority.

Only Home and Markets have product-safe read-only surfaces at this base. The legacy Trading and Portfolio routes contain action controls and are not offered as premium product surfaces. Every other surface returns `SURFACE_NOT_READY`. Unknown, inactive, or missing membership data denies all surfaces. This domain object is a server-side decision contract; no user identity adapter or product access API is wired yet. A frontend must treat an absent canonical decision as denied. It must not infer access from plan labels or visibility of a link.

The contract has no account mutation, PAPER or LIVE execution, billing, or payment capability.
