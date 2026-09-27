import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = fs.readFileSync(new URL("./SimNativeFinancialCard.tsx", import.meta.url), "utf8");
const exports = {};
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
} }).outputText, { exports, require: name => name === "@/lib/dashboardApi" ? {} : require(name) });
const empty = { execution_domain: "SIM_NATIVE", native_account: "Sim101", provider: "Simulator", instrument: "NQ DEC26",
  status: "NO_OPERATION", open_position_count: 0, closed_position_count: 0, journal_count: 0, realized_pnl: 0 };
const render = data => renderToStaticMarkup(React.createElement(exports.SimNativeFinancialView, { data }));

test("no-operation financial view is explicit and has no controls", () => {
  const html = render(empty);
  assert.match(html, /NO OPERATION/);
  assert.match(html, /Open positions/);
  assert.match(html, /Closed trades/);
  assert.match(html, /Journal/);
  assert.match(html, /separado de PAPER/);
  assert.doesNotMatch(html, /<(?:button|input|form)\b|onClick=/);
});

test("native financial facts render without PAPER balance substitution", () => {
  const html = render({ ...empty, status: "CLOSED", direction: "LONG", entry_price: 100, stop_loss: 90, take_profit: 120,
    quantity: 1, exit_price: 120, realized_pnl: 400, order_role: "PROFIT_TARGET", journal_count: 1 });
  for (const text of ["CLOSED", "LONG", "100", "90", "120", "400", "PROFIT_TARGET"]) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /<(?:button|input|form)\b/);
});

test("missing or foreign financial evidence never fabricates zero operation", () => {
  for (const data of [null, { ...empty, execution_domain: "PAPER" }, { ...empty, status: "UNAVAILABLE" }, { ...empty, native_account: "Other" }]) {
    const html = render(data);
    assert.match(html, /UNAVAILABLE/);
    assert.doesNotMatch(html, /NO OPERATION/);
  }
});
