import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./dashboardProjection.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports });

test('empty authoritative journal displays zeroes instead of NaN', () => {
  const result = exports.journalCardData({
    trade_journal_summary: { open_trades: 0, closed_trades: 0, analytics: null },
    analytics: { wins: 0, losses: 0 }, portfolio_summary: { total_realized_pnl: 0 },
    performance_overview: { win_rate: 0 },
  });
  assert.ok(Object.values(result).every(value => value === 0));
  assert.equal(exports.journalCardData(null), null);
});

test('journal uses canonical settled PnL and backend percentage without recalculation', () => {
  const result = exports.journalCardData({
    trade_journal_summary: { open_trades: 1, closed_trades: 1, analytics: { net_profit: 9999, win_rate: .5 } },
    analytics: { wins: 1, losses: 0, win_rate: 1 },
    portfolio_summary: { total_realized_pnl: 25, total_unrealized_pnl: 100 },
    performance_overview: { win_rate: 100 },
  });
  assert.equal(result.total_realized_pnl, 25);
  assert.equal(result.win_rate, 100);
  assert.equal(result.winning_trades, 1);
});
