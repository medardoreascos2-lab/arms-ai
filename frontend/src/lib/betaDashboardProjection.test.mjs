import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const source = fs.readFileSync(new URL("./betaDashboardProjection.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
}}).outputText;
const exports = {};
vm.runInNewContext(compiled, { exports, require: () => ({}) });

function bundle(observed, signalTime, id = "signal-1") {
  return {
    contract_version: "1.0", observed_at: observed, paper_only: true,
    live: { current_signal: "BUY", position: null, signal: {
      signal_id: id, created_at: signalTime, updated_at: signalTime, paper_only: true,
    } },
    performance: { paper_only: true }, history: { records: [] },
    runtime: { read_only: true, live_execution_allowed: false },
  };
}

test("stale and duplicate snapshots cannot replace the last known state", () => {
  const current = bundle("2026-10-06T15:00:00Z", "2026-10-06T14:59:00Z");
  assert.equal(exports.reconcileBetaBundle(current,
    bundle("2026-10-06T14:00:00Z", "2026-10-06T14:00:00Z")), current);
  assert.equal(exports.reconcileBetaBundle(current,
    bundle("2026-10-06T15:00:00Z", "2026-10-06T14:59:00Z")), current);
});

test("new bundle keeps a newer previous signal instead of regressing it", () => {
  const current = bundle("2026-10-06T15:00:00Z", "2026-10-06T14:59:00Z", "new");
  const result = exports.reconcileBetaBundle(current,
    bundle("2026-10-06T15:01:00Z", "2026-10-06T14:00:00Z", "old"));
  assert.equal(result.observed_at, "2026-10-06T15:01:00Z");
  assert.equal(result.live.signal.signal_id, "new");
});

test("non-PAPER contract fails closed", () => {
  const incoming = bundle("2026-10-06T15:00:00Z", "2026-10-06T14:59:00Z");
  incoming.paper_only = false;
  assert.throws(() => exports.reconcileBetaBundle(null, incoming), /PAPER/);
});
test("runtime observation fails closed if browser authority is claimed", () => {
  const incoming = bundle("2026-10-06T15:00:00Z", "2026-10-06T14:59:00Z");
  incoming.runtime.live_execution_allowed = true;
  assert.throws(() => exports.reconcileBetaBundle(null, incoming), /PAPER/);
});
