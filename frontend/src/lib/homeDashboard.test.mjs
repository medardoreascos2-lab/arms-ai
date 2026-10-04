import test from "node:test";
import assert from "node:assert/strict";
import { initialHomeSections } from "./homeDashboard.ts";

test("Home includes truthful multimodal sections in priority order", () => {
  assert.deepEqual(initialHomeSections.map((section) => section.id), [
    "DAILY_INTELLIGENCE", "MARKET_STATUS", "PORTFOLIO_HEALTH", "TRADING_COACH",
    "ALERTS", "TASKS", "RECENT_MEDAR_ACTIVITY", "MEMORY_HIGHLIGHTS",
    "VOICE", "CAMERA", "AVATAR", "PRESENCE", "NOTIFICATIONS", "QUICK_ACTIONS",
  ]);
});

test("unconnected Home data stays unavailable and quick actions use existing routes", () => {
  const dataSections = initialHomeSections.filter((section) => section.id !== "QUICK_ACTIONS");
  assert.ok(dataSections.every((section) => section.content.state === "unavailable"));
  const actions = initialHomeSections.find((section) => section.id === "QUICK_ACTIONS")?.content;
  assert.equal(actions?.state, "navigation");
  assert.deepEqual(actions.actions.map((action) => action.href), [
    "/product/onboarding", "/product/daily-intelligence", "/product/shadow-medar",
    "/product/avatar", "/product/settings/multimodal", "/market-analysis",
  ]);
});

test("unconnected multimodal capabilities disclose their unavailable state", () => {
  const multimodalIds = new Set(["VOICE", "CAMERA", "AVATAR", "PRESENCE", "NOTIFICATIONS"]);
  const multimodal = initialHomeSections.filter((section) => multimodalIds.has(section.id));
  assert.equal(multimodal.length, multimodalIds.size);
  assert.ok(multimodal.every((section) =>
    section.content.state === "unavailable" && section.content.reason.length > 20));
});