import test from "node:test";
import assert from "node:assert/strict";
import { primaryNavigation, linkedNavigation, futureProductAreas } from "./productNavigation.ts";

test("product navigation contains every primary area once", () => {
  const expected = ["HOME", "MEDAR", "MARKETS", "TRADING", "PORTFOLIO", "COACH", "RESEARCH", "ALERTS", "MEMORY", "SETTINGS"];
  assert.deepEqual(primaryNavigation.map((entry) => entry.id), expected);
  assert.equal(new Set(primaryNavigation.map((entry) => entry.id)).size, expected.length);
});

test("only implemented routes are linked and future areas stay out of navigation", () => {
  const linked = linkedNavigation();
  assert.deepEqual(linked.map((entry) => entry.href), ["/product", "/product/medar", "/market-analysis", "/product/trading", "/product/portfolio", "/product/coach"]);
  assert.ok(primaryNavigation.every((entry) => entry.availability === "available" ? Boolean(entry.href) : entry.href === undefined));
  assert.ok(futureProductAreas.every((area) => !linked.some((entry) => entry.id === area.id)));
});
