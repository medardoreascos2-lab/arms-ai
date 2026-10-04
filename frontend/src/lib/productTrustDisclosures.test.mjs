import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { financialDisclosureCopy, financialDisclosureKinds } from "./productTrust.ts";


test("financial disclosure kinds match the Product contract", () => {
  assert.deepEqual(financialDisclosureKinds, ["ANALYSIS", "PAPER", "HYPOTHETICAL", "LIVE_UNAVAILABLE"]);
  assert.match(financialDisclosureCopy.ANALYSIS, /no investment advice or execution authority/i);
  assert.match(financialDisclosureCopy.PAPER, /simulated/i);
  assert.match(financialDisclosureCopy.HYPOTHETICAL, /not actual results/i);
  assert.match(financialDisclosureCopy.LIVE_UNAVAILABLE, /unavailable/i);
});

test("financial Product projections render the shared disclosure strip", () => {
  const shell = readFileSync(new URL("../components/product/FinancialProjectionShell.tsx", import.meta.url), "utf8");
  const daily = readFileSync(new URL("../components/product/DailyIntelligencePanel.tsx", import.meta.url), "utf8");
  assert.match(shell, /<FinancialDisclosureStrip \/>/);
  assert.match(daily, /<FinancialDisclosureStrip \/>/);
});