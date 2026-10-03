# ARMS AI membership policy

## Membership foundation (R28B)

This package models versioned plans, persisted membership status, feature entitlements, usage limits, effective dates, grace periods, and computed expiration. Plans reuse the immutable R28A entitlement types and contain no price, currency, payment-provider ID, or credential.

Membership evaluation and entitlement projection are read-only. Active and grace memberships may project a `UserEntitlementProfile`; pending, suspended, cancelled, expired, missing, mismatched, unavailable, or invalid records fail closed with no profile.

`MembershipReadAdapter` exposes one read method. There is no Stripe integration, payment operation, subscription mutation, billing mutation, authentication authority, account mutation, or trading execution authority.
