import test from "node:test";
import assert from "node:assert/strict";
import { decodeFinancialResponse, isFinancialProjection, requestProductFinancial } from "./productFinancial.ts";

const trading = {
  status: "READY",
  provenance: { source_id: "s1", source_label: "Synthetic fixture",
    classification: "SYNTHETIC", observed_at: "2026-10-04T12:00:00Z",
    freshness_seconds: 0, source_status: "SYNTHETIC" },
  warnings: ["SYNTHETIC LOCAL_TEST_ONLY NOT_REAL_ACCOUNT_DATA"],
  investment_advice: false, execution_authorized: false,
  portfolio_mutation_authorized: false, source_status: "SYNTHETIC",
  instrument: "NQ", market_state: "RANGE", risk_state: "WATCH",
  session_state: "OPEN", data_freshness: "SYNTHETIC_CURRENT",
};

test("Trading projection preserves source states and false authority", () => {
  const value = decodeFinancialResponse(trading);
  assert.equal(isFinancialProjection(value), true);
  assert.equal(value.instrument, "NQ");
  assert.equal(value.execution_authorized, false);
  assert.equal(value.portfolio_mutation_authorized, false);
});

test("Trading client performs one same-origin GET without a body", async () => {
  const calls = [];
  await requestProductFinancial("trading", async (url, init) => {
    calls.push([url, init]); return { ok: true, json: async () => trading };
  });
  assert.deepEqual(calls.map(([url]) => url), ["/api/product/financial/trading"]);
  assert.equal(calls[0][1].method, "GET");
  assert.equal(calls[0][1].body, undefined);
});
