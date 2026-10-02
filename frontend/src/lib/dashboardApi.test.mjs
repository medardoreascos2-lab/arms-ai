import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function client(responses, env = {}) {
  const calls = [];
  const source = fs.readFileSync(path.join(__dirname, "dashboardApi.ts"), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, {
    exports, process: { env }, URL, btoa,
    WebSocket: class { constructor(url, protocols) { this.url = url; this.protocols = protocols; } },
    fetch: async (url, options) => {
      calls.push({ url, options });
      const response = typeof responses === 'function' ? responses(url, options) : responses.shift();
      assert.ok(response, "Unexpected request");
      return { ok: response.ok ?? true, status: response.status ?? 200,
        json: async () => response.body };
    },
  });
  exports.configurePaperCredential("test-paper-admin");
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

test("only protected requests carry the canonical credential", async () => {
  const c = client([{ body: {} }, { body: {} }]);
  await c.api.getDashboardLive();
  await c.api.requestJson('/api/v2/dashboard/account-manager/switch', {}, true);
  assert.equal(c.calls[0].options.headers['X-ARMS-ADMIN-TOKEN'], undefined);
  assert.equal(c.calls[1].options.headers['X-ARMS-ADMIN-TOKEN'], 'test-paper-admin');
  assert.equal(c.calls[1].options.redirect, 'error');
  assert.equal(c.calls[1].options.credentials, 'omit');
});

test("SIM_NATIVE observations use a separate unprivileged abortable GET", async () => {
  const c = client([{ body: { execution_domain: "SIM_NATIVE", status: "HEALTHY" } }]);
  const controller = new AbortController();
  const result = await c.api.getSimNativeRuntime(controller.signal);
  assert.equal(result.execution_domain, "SIM_NATIVE");
  assert.equal(c.calls.length, 1);
  assert.equal(c.calls[0].url, "http://localhost:8000/api/v3/dashboard/sim-native-runtime");
  assert.equal(c.calls[0].options.method, "GET");
  assert.equal(c.calls[0].options.body, undefined);
  assert.equal(c.calls[0].options.headers["X-ARMS-ADMIN-TOKEN"], undefined);
  assert.equal(c.calls[0].options.signal, controller.signal);
});

test("SIM_NATIVE reader rejects a PAPER response instead of merging contracts", async () => {
  const c = client([{ body: { execution_domain: "PAPER" } }]);
  await assert.rejects(c.api.getSimNativeRuntime(), /SIM_NATIVE/);
});

test("SIM_NATIVE financial reader is a separate credential-free GET and rejects PAPER", async () => {
  const c = client([{ body: { execution_domain: "SIM_NATIVE", status: "NO_OPERATION" } }, { body: { execution_domain: "PAPER" } }]);
  const controller = new AbortController();
  assert.equal((await c.api.getSimNativeFinancial(controller.signal)).status, "NO_OPERATION");
  assert.equal(c.calls[0].url, "http://localhost:8000/api/v3/dashboard/sim-native-financial");
  assert.equal(c.calls[0].options.method, "GET");
  assert.equal(c.calls[0].options.headers["X-ARMS-ADMIN-TOKEN"], undefined);
  assert.equal(c.calls[0].options.signal, controller.signal);
  await assert.rejects(c.api.getSimNativeFinancial(), /SIM_NATIVE/);
});

test("analysis and Current-PAPER reads use distinct origins without credentials or mutation", async () => {
  const c = client([{body:{}}, {body:{}}, {body:{}}], {
    NEXT_PUBLIC_API_URL: 'http://127.0.0.1:18001',
    NEXT_PUBLIC_CURRENT_PAPER_API_URL: 'http://127.0.0.1:18002',
  });
  const controller = new AbortController();
  await c.api.requestJson('/api/v2/market-analysis/time-profile');
  await c.api.getBacktestingDashboard();
  await c.api.requestCurrentPaperJson('/api/v2/backtesting/dashboard', controller.signal);
  assert.equal(c.calls[0].url, 'http://127.0.0.1:18001/api/v2/market-analysis/time-profile');
  assert.equal(c.calls[1].url, 'http://127.0.0.1:18001/api/v2/backtesting/dashboard');
  assert.equal(c.calls[2].url, 'http://127.0.0.1:18002/api/v2/backtesting/dashboard');
  assert.equal(c.calls[2].options.signal, controller.signal);
  assert.ok(c.calls.every(call => call.options.method === 'GET' &&
    call.options.body === undefined && call.options.headers['X-ARMS-ADMIN-TOKEN'] === undefined));
  controller.abort();
  assert.equal(c.calls[2].options.signal.aborted, true);
});

test("Current-PAPER rejects missing or invalid public origins before a request", async () => {
  for (const origin of [undefined, '', 'http://remote.example',
    'http://user:secret@127.0.0.1:18002', 'http://127.0.0.1:18002/path',
    'http://127.0.0.1:18002/?token=secret', 'http://127.0.0.1:18002/#fragment']) {
    const c = client([], { NEXT_PUBLIC_CURRENT_PAPER_API_URL: origin });
    await assert.rejects(c.api.requestCurrentPaperJson('/api/v2/backtesting/dashboard'));
    assert.equal(c.calls.length, 0);
  }
  const c = client([], { NEXT_PUBLIC_CURRENT_PAPER_API_URL: 'https://paper.example' });
  await assert.rejects(c.api.requestCurrentPaperJson('//remote.example/path'), /inválida/);
  assert.equal(c.calls.length, 0);
});

test("Current-PAPER accepts HTTPS without attaching the configured admin credential", async () => {
  const c = client([{body:{status:'READY'}}], {
    NEXT_PUBLIC_CURRENT_PAPER_API_URL: 'https://paper.example',
  });
  assert.equal((await c.api.requestCurrentPaperJson('/api/v2/backtesting/dashboard')).status, 'READY');
  assert.equal(c.calls[0].url, 'https://paper.example/api/v2/backtesting/dashboard');
  assert.equal(c.calls[0].options.headers['X-ARMS-ADMIN-TOKEN'], undefined);
});

test("paper-current page polls only the Current-PAPER read endpoint", () => {
  const source = fs.readFileSync(path.join(__dirname, '../app/paper-current/page.tsx'), 'utf8');
  assert.equal((source.match(/requestCurrentPaperJson\(/g) ?? []).length, 1);
  assert.ok(source.includes('requestCurrentPaperJson("/api/v2/backtesting/dashboard", request.signal)'));
  assert.ok(source.includes('setTimeout(poll, 2000)'));
  assert.ok(source.includes('pending?.abort()'));
  assert.equal(/requestJson\(|<button|<form|\/api\/v2\/paper\/|\/control/.test(source), false);
});

test("missing credential cannot send a protected command or open a socket", async () => {
  const c = client([]);
  c.api.configurePaperCredential('');
  await assert.rejects(c.api.requestJson('/control', {}, true), /credencial/);
  assert.throws(() => c.api.openDashboardWebSocket(), /credencial/);
  assert.equal(c.calls.length, 0);
});

test("wrong credential failure is surfaced without retry or mutation fallback", async () => {
  const c = client([{ ok: false, status: 401, body: { detail: 'admin_unauthorized' } }]);
  c.api.configurePaperCredential('wrong');
  await assert.rejects(c.api.requestJson('/control', {}, true), /admin_unauthorized/);
  assert.equal(c.calls.length, 1);
});

test("WebSocket uses same credential in protocol and never in URL", () => {
  const c = client([]);
  const ws = c.api.openDashboardWebSocket();
  assert.equal(ws.url, 'ws://localhost:8000/api/v2/dashboard/ws');
  assert.equal(ws.protocols[0], 'arms-dashboard-v1');
  assert.equal(ws.protocols[1], 'arms-admin.' + Buffer.from('test-paper-admin').toString('base64url'));
});

test("insecure remote origin fails before sending a credential", async () => {
  const c = client([], { NEXT_PUBLIC_API_URL: 'http://remote.example' });
  await assert.rejects(c.api.requestJson('/control', {}, true), /HTTPS/);
  assert.equal(c.calls.length, 0);
});

test("AI decision reads backend intelligence without demo metrics", async () => {
  const c = client([{ body: { decision: 'WAIT' } }]);
  await c.api.getAIDecision();
  assert.equal(c.calls[0].options.method, 'GET');
  assert.equal(c.calls[0].options.body, undefined);
});

test("bundle excludes demonstration approvals and preserves authoritative snapshot values", async () => {
  const identity = { account_id: 'PAPER-A', profile_name: 'A', runtime_generation: 1 };
  const snapshot = { runtime: identity, execution_mode: 'PAPER', account_state: { balance: 150020 },
    risk_status: { trading_blocked: true }, portfolio_summary: { total_realized_pnl: 20 } };
  const c = client(url => ({ body: url.endsWith('/switch-context') ? identity :
    url.endsWith('/live') ? snapshot : {} }));
  const result = await c.api.getDashboardBundle();
  assert.equal(result.live, snapshot);
  assert.ok(c.calls.every(call => call.options.method === 'GET'));
  for (const suffix of ['/trade-setup', '/execution-approval', '/execution-simulator', '/strategy-ranking', '/confidence-fusion', '/intelligence-decision']) {
    assert.ok(c.calls.every(call => !call.url.endsWith(suffix)), suffix);
  }
});

test("bundle rejects account generation changes during parallel reads", async () => {
  let contexts = 0;
  const identity = { account_id: 'PAPER-A', profile_name: 'A', runtime_generation: 1 };
  const c = client(url => ({ body: url.endsWith('/switch-context') ?
    { ...identity, runtime_generation: ++contexts } :
    url.endsWith('/live') ? { runtime: identity, execution_mode: 'PAPER' } : {} }));
  await assert.rejects(c.api.getDashboardBundle(), /runtime PAPER cambió/);
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


test("coordinated switch sends target B identity, never current A identity", async () => {
  const c = client([
    { body: { account_id: "PAPER-A", profile_name: "A", accounts: [
      { account_id: "PAPER-A", profile_name: "A" }, { account_id: "PAPER-B", profile_name: "B" },
    ] } },
    { body: { status: "ACCOUNT_CHANGED", changed: true } },
  ]);
  assert.equal((await c.api.switchAccount("B")).changed, true);
  assert.deepEqual(JSON.parse(c.calls[1].options.body),
    { account_id: "PAPER-B", profile_name: "B" });
});

test("ambiguous profile requires explicit account identity before POST", async () => {
  const c = client([{ body: { account_id: "PAPER-ONE", accounts: [
    { account_id: "PAPER-ONE", profile_name: "A" }, { account_id: "PAPER-TWO", profile_name: "A" },
  ] } }]);
  await assert.rejects(c.api.switchAccount("A"), /identidad/);
  assert.equal(c.calls.length, 1);
});

test("two accounts sharing a profile can be selected by explicit identity", async () => {
  const c = client([
    { body: { account_id: "PAPER-ONE", accounts: [
      { account_id: "PAPER-ONE", profile_name: "A" }, { account_id: "PAPER-TWO", profile_name: "A" },
    ] } },
    { body: { status: "ACCOUNT_CHANGED", changed: true } },
  ]);
  await c.api.switchAccount("A", "PAPER-TWO");
  assert.deepEqual(JSON.parse(c.calls[1].options.body),
    { account_id: "PAPER-TWO", profile_name: "A" });
});
