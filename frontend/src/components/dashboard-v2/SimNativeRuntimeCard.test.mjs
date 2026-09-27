import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = fs.readFileSync(new URL("./SimNativeRuntimeCard.tsx", import.meta.url), "utf8");
const exports = {};
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
} }).outputText, { exports, require: name => name === "@/lib/dashboardApi" ? {} : require(name) });

const healthy = {
  execution_domain: "SIM_NATIVE", status: "HEALTHY", native_account: "Sim101", provider: "Simulator", instrument: "NQ DEC26",
  heartbeat_fresh: true, heartbeat_age_seconds: 1, heartbeat_maximum_age_seconds: 15,
  connection_status: "Connected", physical_test_readiness: "PHYSICAL_TEST_READY", position_state: "FLAT", active_order_count: 0,
  controlled_v3_configured: true, authority_loaded: true, config_signature_valid: true, reconciliation_fence: false,
  native_submit_enabled: false, auto_retry_allowed: false, command_path_ready: true, activation_path_ready: true,
  state_path_ready: true, reconciliation_path_ready: true, restore_status: "NO_PERSISTED_OPERATION", observed_at: "2026-09-27T18:00:00Z",
};
const render = (data, elapsedSeconds = 0) => renderToStaticMarkup(React.createElement(exports.SimNativeRuntimeView, { data, elapsedSeconds }));

test("healthy SIM_NATIVE observations render independently with no execution controls", () => {
  const html = render(healthy);
  for (const text of ["SIM_NATIVE / Sim101", "NQ DEC26", "Connected", "Fresh", "FLAT", "HEALTHY", "DISABLED", "separados de PAPER"])
    assert.ok(html.includes(text), text);
  assert.match(html, /border-emerald/);
  assert.doesNotMatch(html, /<(?:button|form|input)\b|onClick=/);
});

test("stale heartbeat is visible and can age out without a new response", () => {
  for (const html of [render({ ...healthy, status: "STALE", heartbeat_fresh: false }), render(healthy, 15)]) {
    assert.match(html, /STALE/);
    assert.match(html, /border-amber/);
    assert.doesNotMatch(html, /border-emerald/);
  }
});

test("market closed is a session warning, not a runtime failure", () => {
  const html = render({ ...healthy, status: "SESSION_CLOSED", physical_test_readiness: "MARKET_SESSION_CLOSED" });
  assert.match(html, /Mercado cerrado · MARKET_SESSION_CLOSED/);
  assert.match(html, /border-amber/);
  assert.doesNotMatch(html, /border-rose|REVISAR/);
});

for (const change of [{config_signature_valid:false}, {reconciliation_fence:true}, {connection_status:"Disconnected"},
  {native_submit_enabled:true}, {auto_retry_allowed:true}, {controlled_v3_configured:false}]) {
  test(`unsafe observation is red: ${JSON.stringify(change)}`, () => {
    const html = render({ ...healthy, ...change });
    assert.match(html, /border-rose/);
    assert.doesNotMatch(html, /border-emerald|<(?:button|form|input)\b/);
  });
}

test("missing observation does not invent disabled capabilities or a connection", () => {
  for (const data of [null, {execution_domain: "SIM_NATIVE", status: "UNAVAILABLE", heartbeat_fresh: false}]) {
    const html = render(data);
    assert.match(html, /UNAVAILABLE/);
    assert.match(html, /Sin observación/);
    assert.doesNotMatch(html, /DISABLED|Connected|border-emerald|STALE/);
  }
});

test("page keeps the PAPER runtime separate", () => {
  const page = fs.readFileSync(new URL("../../app/dashboard-v2/page.tsx", import.meta.url), "utf8");
  assert.match(page, /<SimNativeRuntimeCard\s*\/>/);
  assert.match(page, /Modo: PAPER/);
  assert.match(page, /configurePaperCredential\(credential\)/);
});
