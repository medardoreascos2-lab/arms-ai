import test from "node:test";
import assert from "node:assert/strict";
import { securityCenterItems } from "./productSecurity.ts";

test("Security Center exposes required read-only areas and denied permissions", () => {
  assert.deepEqual(securityCenterItems.map((item) => item.id), [
    "SESSIONS", "EVENTS", "MFA", "PASSKEYS", "PERMISSIONS",
  ]);
  assert.equal(
    securityCenterItems.find((item) => item.id === "PERMISSIONS").status,
    "DENIED",
  );
  assert.ok(securityCenterItems
    .filter((item) => item.id === "MFA" || item.id === "PASSKEYS")
    .every((item) => item.status === "INTEGRATION_PENDING"));
});
