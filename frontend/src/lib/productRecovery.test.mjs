import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { degradedProductState, degradedProductStatuses } from "./productRecovery.ts";


test("degraded statuses and safe actions match the recovery contract", () => {
  assert.deepEqual(degradedProductStatuses, [
    "MODEL_UNAVAILABLE", "MEMORY_UNAVAILABLE", "FINANCIAL_DATA_UNAVAILABLE",
    "AUTH_UNAVAILABLE", "PAYMENT_PROVIDER_UNAVAILABLE", "NETWORK_UNAVAILABLE",
    "PERMISSION_BLOCKED",
  ]);
  for (const status of degradedProductStatuses) {
    const state = degradedProductState(status, "Unavailable", "error-1");
    assert.equal(state.data, null);
    assert.equal(state.syntheticFallbackUsed, false);
    assert.deepEqual(state.actions, ["RETRY", "REFRESH", "DETAILS", "REPORT_ISSUE"]);
  }
});

test("recovery UI contains no execution or fake-data side effects", () => {
  const source = readFileSync(new URL("../components/product/DegradedRecoveryPanel.tsx", import.meta.url), "utf8");
  for (const label of ["Retry", "Refresh", "Details", "Report issue"]) assert.match(source, new RegExp(label));
  assert.match(source, /No fallback data has been substituted/);
  assert.doesNotMatch(source, /fetch\(|order|trade|portfolio|mock|fixture/i);
});

test("financial degraded states use the shared recovery panel", () => {
  const source = readFileSync(new URL("../components/product/FinancialProjectionShell.tsx", import.meta.url), "utf8");
  assert.match(source, /<DegradedRecoveryPanel/);
  assert.match(source, /status="FINANCIAL_DATA_UNAVAILABLE"/);
});