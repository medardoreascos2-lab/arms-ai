import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = fs.readFileSync(new URL('./dashboardConnection.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020,
} }).outputText;
const identity = (account_id = 'A', runtime_generation = 1) => ({ account_id, profile_name: account_id, runtime_generation });
const bundle = (id = identity()) => ({ context: id, live: { runtime: id, account_state: { balance: 51234.56 }, risk_status: { trading_blocked: true } } });
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness() {
  const sockets = [], publications = [], statuses = [], errors = [], timers = new Map();
  let counter = 0, read = async () => bundle(), switching = async () => ({});
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: () => ({
    getDashboardBundle: () => read(), switchAccount: (...args) => switching(...args),
    runtimeKey: id => JSON.stringify([id.account_id, id.profile_name, id.runtime_generation]),
    openDashboardWebSocket: () => { const socket = { close() { this.closed = true; } }; sockets.push(socket); return socket; },
  }), setTimeout: f => { timers.set(++counter, f); return counter; }, clearTimeout: id => timers.delete(id),
  setInterval: f => { timers.set(++counter, f); return counter; }, clearInterval: id => timers.delete(id) });
  const client = new exports.DashboardConnection(v => publications.push(v), s => statuses.push(s), e => errors.push(e));
  const message = (socket, id = identity()) => socket.onmessage({ data: JSON.stringify({ event_type: 'dashboard_snapshot', data: { runtime: id, execution_mode: 'PAPER' } }) });
  return { client, sockets, publications, statuses, errors, timers, message,
    read: fn => { read = fn; }, switching: fn => { switching = fn; } };
}

test('authorized snapshot publishes unchanged backend financial/risk values', async () => {
  const h = harness(); h.client.start(); h.message(h.sockets[0]); await flush();
  assert.equal(h.publications.at(-1).live.account_state.balance, 51234.56);
  assert.equal(h.publications.at(-1).live.risk_status.trading_blocked, true);
  assert.equal(h.statuses.at(-1), 'CONNECTED'); h.client.stop();
});

test('retired socket messages and delayed HTTP completions cannot republish A', async () => {
  const h = harness(); let complete;
  h.read(() => new Promise(resolve => { complete = resolve; }));
  h.client.start(); const old = h.sockets[0]; h.message(old);
  old.onclose({ code: 1012 });
  complete(bundle()); await flush(); h.message(old); await flush();
  assert.equal(h.publications.at(-1), null);
  const reconnect = [...h.timers.values()][0]; reconnect();
  h.read(async () => bundle(identity('B', 2))); h.message(h.sockets[1], identity('B', 2)); await flush();
  assert.equal(h.publications.at(-1).context.account_id, 'B'); h.client.stop();
});

test('local account switch clears every projection before protected request resolves', async () => {
  const h = harness(); h.client.start(); h.message(h.sockets[0]); await flush();
  let complete; h.switching((profile, account) => { assert.equal(profile, 'B'); assert.equal(account, 'B'); return new Promise(r => { complete = r; }); });
  const switching = h.client.switch('B', 'B');
  assert.equal(h.publications.at(-1), null); assert.equal(h.sockets[0].closed, true);
  complete({}); await switching; assert.equal(h.sockets.length, 2); h.client.stop();
});

test('A to B to A with new generation discards the stale bundle', async () => {
  const h = harness(); h.read(async () => bundle(identity('A', 3)));
  h.client.start(); h.message(h.sockets[0]); await flush();
  assert.ok(h.publications.every(v => v === null));
  assert.equal(h.sockets[0].closed, true); h.client.stop();
});

test('rejected auth clears projections and does not retry credentials indefinitely', () => {
  for (const code of [1008, 1006]) {
    const h = harness(); h.client.start(); h.sockets[0].onclose({ code });
    assert.equal(h.publications.at(-1), null); assert.equal(h.timers.size, 0);
    assert.match(h.errors.at(-1), /rechazada/);
  }
});

test('failed switch and unavailable HTTP remain empty and report failure', async () => {
  const h = harness(); h.client.start(); h.message(h.sockets[0]); await flush();
  h.read(async () => { throw new Error('runtime_unavailable'); }); await h.client.refresh();
  assert.equal(h.publications.at(-1), null);
  h.switching(async () => { throw new Error('switch_rejected'); }); await h.client.switch('B', 'B');
  assert.equal(h.publications.at(-1), null); assert.equal(h.statuses.at(-1), 'ERROR');
});

test('LIVE snapshot is rejected before HTTP reads or publication', () => {
  const h = harness(); h.client.start();
  h.sockets[0].onmessage({ data: JSON.stringify({ event_type: 'dashboard_snapshot', data: { execution_mode: 'LIVE' } }) });
  assert.equal(h.statuses.at(-1), 'ERROR'); assert.ok(h.publications.every(v => v === null));
});
