import test from "node:test";
import assert from "node:assert/strict";
import { localFinancialEnabled, localFinancialEndpoint } from "./financialLocalConfig.ts";
import { decodeFinancialResponse, isFinancialProjection, requestProductFinancial } from "./productFinancial.ts";

const ready = {
  status: "READY",
  provenance: { source_id: "synthetic-source", source_label: "Synthetic fixture",
    classification: "SYNTHETIC", observed_at: "2026-10-04T12:00:00Z",
    freshness_seconds: 0, source_status: "SYNTHETIC" },
  warnings: ["SYNTHETIC LOCAL_TEST_ONLY NOT_REAL_ACCOUNT_DATA"],
  investment_advice: false, execution_authorized: false,
  portfolio_mutation_authorized: false, source_status: "SYNTHETIC",
  headline: "Synthetic daily snapshot",
};

test("financial local config requires nonproduction enablement and loopback", () => {
  assert.equal(localFinancialEnabled({
    NODE_ENV: "development", PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED: "true",
  }), true);
  assert.equal(localFinancialEnabled({
    NODE_ENV: "production", PRODUCT_FINANCIAL_LOCAL_TEST_ENABLED: "true",
  }), false);
  assert.equal(localFinancialEndpoint("http://127.0.0.1:8002/", "overview"),
    "http://127.0.0.1:8002/product/financial/overview");
  assert.equal(localFinancialEndpoint("https://example.com/", "overview"), null);
});

test("financial decoder requires provenance and fixed-false authority", () => {
  assert.equal(isFinancialProjection(decodeFinancialResponse(ready)), true);
  for (const invalid of [
    { ...ready, provenance: undefined }, { ...ready, execution_authorized: true },
    { ...ready, portfolio_mutation_authorized: true },
  ]) assert.equal(decodeFinancialResponse(invalid).status, "FINANCIAL_DATA_UNAVAILABLE");
});

test("degraded responses cannot claim authority or data", () => {
  assert.equal(decodeFinancialResponse({
    status: "STALE_DATA", data: null, broker_authorized: false,
    portfolio_mutation_authorized: false, paper_authorized: false, live_authorized: false,
  }).status, "STALE_DATA");
  assert.equal(decodeFinancialResponse({
    status: "ENTITLEMENT_REQUIRED", data: ready, broker_authorized: false,
    portfolio_mutation_authorized: false, paper_authorized: false, live_authorized: false,
  }).status, "FINANCIAL_DATA_UNAVAILABLE");
});

test("financial client uses only same-origin GET route", async () => {
  const calls = [];
  const response = await requestProductFinancial("overview", async (url, init) => {
    calls.push([url, init]); return { ok: true, json: async () => ready };
  });
  assert.equal(isFinancialProjection(response), true);
  assert.deepEqual(calls.map(([url]) => url), ["/api/product/financial/overview"]);
  assert.equal(calls[0][1].method, "GET");
  assert.equal(calls[0][1].body, undefined);
});
