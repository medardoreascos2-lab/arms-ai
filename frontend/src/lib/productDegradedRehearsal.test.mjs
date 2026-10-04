import test from "node:test";
import assert from "node:assert/strict";
import { degradedResponse } from "./medarProduct.ts";
import { degradedFinancialResponse } from "./productFinancial.ts";
import { degradedProductState } from "./productRecovery.ts";


test("model-down and memory-down flows remain truthful", () => {
  for (const status of ["MODEL_UNAVAILABLE", "MEMORY_UNAVAILABLE"]) {
    const response = degradedResponse("request-e2e", status);
    assert.equal(response.answer, null);
    assert.equal(response.confidence, null);
    assert.equal(response.reasoning_summary, null);
    assert.deepEqual(response.sources, []);
    assert.deepEqual(response.memory_context, []);
    assert.deepEqual(response.action_proposals, []);
  }
});

test("unknown financial flow has no data or authority", () => {
  const response = degradedFinancialResponse("FINANCIAL_DATA_UNAVAILABLE");
  assert.equal(response.data, null);
  assert.equal(response.broker_authorized, false);
  assert.equal(response.paper_authorized, false);
  assert.equal(response.live_authorized, false);
  assert.equal(response.portfolio_mutation_authorized, false);
});

test("billing-provider and network recovery never substitute data", () => {
  for (const status of ["PAYMENT_PROVIDER_UNAVAILABLE", "NETWORK_UNAVAILABLE"]) {
    const state = degradedProductState(status, "Service unavailable", "synthetic-error-e2e");
    assert.equal(state.data, null);
    assert.equal(state.syntheticFallbackUsed, false);
    assert.deepEqual(state.actions, ["RETRY", "REFRESH", "DETAILS", "REPORT_ISSUE"]);
  }
});