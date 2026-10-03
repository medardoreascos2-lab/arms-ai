# ARMS AI user entitlements

## User, role, and entitlement domain (R28A)

This package models opaque user identity, tenant roles, derived permissions, feature entitlements, account and daily signal limits, read-only dashboard access, and read/test notification access.

It is deliberately separate from `AdminAuthorizationV2`, FastAPI dependencies, account runtime state, and execution authority. A tenant role or entitlement never authenticates a request, supplies an admin credential, grants PAPER or LIVE execution, or mutates an account. Every profile and decision reports `canonical_admin_authorized=false` and `execution_authorized=false`.

Roles provide a fixed immutable permission set. Features and access levels remain independent gates, so a role alone cannot enable a product feature. Capacity checks are pure calculations over caller-supplied counts and do not reserve or mutate usage.

This milestone has no pricing or membership lifecycle.
