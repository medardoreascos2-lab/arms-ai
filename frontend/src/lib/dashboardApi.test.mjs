import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function client(responses) {
  const calls = [];
  const source = fs.readFileSync(path.join(__dirname, "dashboardApi.ts"), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports,
    fetch: async (url, options) => {
      calls.push({ url, options });
      const response = responses.shift();
      assert.ok(response, "Unexpected request");
      return { ok: response.ok ?? true, status: response.status ?? 200,
        json: async () => response.body };
    },
  });
  return { api: exports, calls };
}

test("switch posts canonical operational identity and separate profile using JSON", async () => {
  const c = client([
    { body: { account_id: "ARMS-PAPER-LIFECYCLE", profile_name: "A" } },
    { body: { status: "ACCOUNT_UNCHANGED", changed: false } },
  ]);
  const result = await c.api.switchAccount("A");
  assert.equal(result.status, "ACCOUNT_UNCHANGED");
  assert.equal(c.calls.length, 2);
  assert.equal(c.calls[0].url, "http://localhost:8000/api/v2/dashboard/account-manager/switch-context");
  assert.equal(c.calls[1].url, "http://localhost:8000/api/v2/dashboard/account-manager/switch");
  assert.equal(c.calls[1].options.method, "POST");
  assert.deepEqual(JSON.parse(c.calls[1].options.body),
    { account_id: "ARMS-PAPER-LIFECYCLE", profile_name: "A" });
});

test("rejected switch propagates failure so dashboard does not publish success", async () => {
  const c = client([
    { body: { account_id: "ARMS-PAPER-LIFECYCLE", profile_name: "A" } },
    { ok: false, status: 409, body: { detail: "Account unchanged." } },
  ]);
  await assert.rejects(c.api.switchAccount("B"), /Account unchanged/);
  assert.deepEqual(JSON.parse(c.calls[1].options.body),
    { account_id: "ARMS-PAPER-LIFECYCLE", profile_name: "B" });
});

test("missing operational identity never sends a switch", async () => {
  const c = client([{ body: { profile_name: "A" } }]);
  await assert.rejects(c.api.switchAccount("B"), /No se pudo verificar/);
  assert.equal(c.calls.length, 1);
});
