import test from "node:test";
import assert from "node:assert/strict";
import { initialDailyInsights } from "./dailyIntelligence.ts";

test("Daily Intelligence starts with honest unavailable sections", () => {
  assert.deepEqual(initialDailyInsights.map((item) => item.id), ["BRIEF", "MARKET", "PORTFOLIO", "PRIORITIES"]);
  assert.ok(initialDailyInsights.every((item) => item.content.state === "unavailable"));
  assert.ok(initialDailyInsights.every((item) => item.content.reason.includes("No verified daily source")));
  assert.equal(JSON.stringify(initialDailyInsights).includes("$"), false);
});
