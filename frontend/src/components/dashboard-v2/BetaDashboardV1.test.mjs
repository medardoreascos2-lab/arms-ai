import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const component = fs.readFileSync(new URL("./BetaDashboardV1.tsx", import.meta.url), "utf8");
const page = fs.readFileSync(new URL("../../app/dashboard-v2/page.tsx", import.meta.url), "utf8");

test("existing dashboard route mounts an observation-only owner console", () => {
  assert.match(page, /return <BetaDashboardV1 \/>;/);
  assert.doesNotMatch(page, /BetaDashboardV1 adminView=/);
  assert.match(component, /user\.role === "admin"/);
  assert.match(component, /OWNER CONSOLE/);
  assert.match(component, /LIVE/);
  assert.match(component, /HISTORY/);
  assert.match(component, /PERFORMANCE/);
  assert.match(component, /Username or email/);
  assert.match(component, /type="text" autoComplete="username"/);
});

test("beta view is explicitly simulated and contains no trading command UI", () => {
  assert.match(component, /PAPER \/ SIMULATED RESULTS/);
  assert.match(component, /NOT LIVE BROKER PERFORMANCE/);
  assert.match(component, /No browser execution authority/);
  assert.match(component, /Read-only runtime observation/);
  assert.match(component, /NinjaTrader/);
  assert.match(component, /Order submission unreachable from dashboard/);
  for (const forbidden of [
    "submitOrder", "placeOrder", "enablePaper", "enableLive", "switchAccount",
    "/market/webhook", "/v2/trades/submit",
  ]) assert.equal(component.includes(forbidden), false, forbidden);
});

test("owner console displays independent session, freshness, runtime, and authorities", () => {
  for (const field of [
    "runtime.market_session_status",
    "runtime.feed_freshness",
    "runtime.paper_runtime_health",
    "runtime.paper_execution_authority",
    "runtime.live_execution_authority",
  ]) assert.match(component, new RegExp(field.replace(".", "\\.")));
});
