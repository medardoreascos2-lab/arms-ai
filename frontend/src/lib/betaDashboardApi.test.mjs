import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function harness(responses) {
  const source = fs.readFileSync(new URL("./betaDashboardApi.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
  }}).outputText;
  const calls = [];
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, URL, DOMException,
    process: { env: { NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000" } },
    fetch: async (url, options) => {
      calls.push({ url, options });
      const next = responses.shift();
      assert.ok(next, `Unexpected request to ${url}`);
      return { ok: next.ok ?? true, status: next.status ?? 200,
        json: async () => next.body };
    },
  });
  return { api: exports, calls, source };
}

test("beta session uses cookies and keeps the CSRF token out of URLs and bodies", async () => {
  const h = harness([
    { body: { user: { role: "admin" }, csrf_token: "csrf-value" } },
    { body: { counts: {}, users: [] } },
    { body: { user: { user_id: "u1" } } },
  ]);
  await h.api.loginBeta("admin@example.com", "not-logged-by-client");
  await h.api.getBetaUsers();
  await h.api.extendBetaUser("u1", 30);
  assert.ok(h.calls.every(call => call.options.credentials === "include"));
  assert.ok(h.calls.every(call => !call.url.includes("csrf-value")));
  assert.equal(h.calls[1].options.method, "GET");
  assert.equal(h.calls[1].options.body, undefined);
  assert.equal(h.calls[2].options.headers["X-ARMS-BETA-CSRF"], "csrf-value");
  assert.equal(JSON.parse(h.calls[2].options.body).days, 30);
});

test("beta product data is fetched only through one authenticated read endpoint", async () => {
  const bundle = { contract_version: "1.0", paper_only: true };
  const h = harness([{ body: bundle }]);
  assert.equal(await h.api.getBetaDashboard(), bundle);
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0].url, "http://127.0.0.1:8000/api/v1/beta/dashboard");
  assert.equal(h.calls[0].options.method, "GET");
  assert.equal(h.calls[0].options.body, undefined);
});

test("beta client contains no trading, runtime-control, secret storage, or socket path", () => {
  const h = harness([]);
  for (const forbidden of [
    "/orders", "/trades/submit", "paper/enable", "live/enable",
    "account/switch", "/ninjatrader", "localStorage", "sessionStorage", "WebSocket",
    "NEXT_PUBLIC_ADMIN", "Authorization",
  ]) assert.equal(h.source.includes(forbidden), false, forbidden);
});
