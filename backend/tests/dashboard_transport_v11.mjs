import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import ts from 'typescript';

const exports = {}, calls = [];
const source = fs.readFileSync('src/lib/dashboardApi.ts', 'utf8');
vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText, { exports, URL, btoa, WebSocket,
  process: { env: { NEXT_PUBLIC_API_URL: `http://127.0.0.1:${process.argv[2]}` } },
  fetch: (url, options) => { calls.push({ url, options }); return fetch(url, options); },
});
const api = exports;
api.configurePaperCredential('admin-secret'); // isolated test fixture credential
const snapshot = socket => new Promise((resolve, reject) => {
  socket.onmessage = event => resolve(JSON.parse(event.data)); socket.onerror = reject;
});
const ws = api.openDashboardWebSocket();
const event = await snapshot(ws);
assert.equal(event.event_type, 'dashboard_snapshot');
const a = await api.getDashboardBundle();
assert.equal(a.live.runtime.account_id, event.data.runtime.account_id);
assert.equal(a.live.account_state.balance, event.data.account_state.balance);
assert.equal(a.live.portfolio_summary.total_realized_pnl, event.data.portfolio_summary.total_realized_pnl);
assert.ok(a.live.journal_history.length > 0);
assert.equal(a.market.signal_v2.source, 'LIVE_MARKET_ANALYSIS');
assert.equal(a.market.signal_v2.account_id, a.context.account_id);
assert.equal(a.market.signal_v2.source_hash.length, 64);
assert.equal(a.market.market_data.snapshot_only, true);
assert.ok(calls.every(c => c.options.method === 'GET'));
assert.ok(calls.every(c => !c.options.headers['X-ARMS-ADMIN-TOKEN']));
const target = a.context.accounts.find(row => row.profile_name === 'B');
const retired = new Promise(resolve => { ws.onclose = resolve; });
await api.switchAccount(target.profile_name, target.account_id);
assert.equal((await retired).code, 1012);
const wsB = api.openDashboardWebSocket();
const eventB = await snapshot(wsB);
const b = await api.getDashboardBundle();
assert.equal(b.live.runtime.account_id, eventB.data.runtime.account_id);
assert.notEqual(b.live.runtime.account_id, a.live.runtime.account_id);
assert.equal(b.live.journal_history.length, 0);
assert.equal(b.market.status, 'UNAVAILABLE');
const closed = new Promise(resolve => { wsB.onclose = resolve; });
wsB.close(); await closed;
const commands = calls.filter(c => c.options.method === 'POST');
assert.equal(commands.length, 1);
assert.equal(commands[0].options.headers['X-ARMS-ADMIN-TOKEN'], 'admin-secret');
console.log('V11_HTTP_WS_BUNDLE_GREEN');
