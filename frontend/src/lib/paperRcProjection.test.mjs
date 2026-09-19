import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./paperRcProjection.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports });

test('PAPER card uses canonical values without recomputing account or score', () => {
  const input = { mode:'PAPER_RESEARCH', paper_ready:false, account_overview:{balance:151170,equity:151000,daily_pnl:1170},
    strategy_evidence:{confluence:{score:81.33},quality:{score:85}}, configuration:{boundary:80.5,quality:85},
    journal_completed:1, active_simulated_positions:[] };
  const before = JSON.stringify(input);
  const rows = Object.fromEntries(exports.paperRcRows(input));
  assert.equal(rows.BALANCE,151170);
  assert.equal(rows.EQUITY,151000);
  assert.equal(rows['PAPER STATUS'],'BLOCKED');
  assert.equal(rows['CONFLUENCE THRESHOLD'],80.5);
  assert.equal(rows.CONFLUENCE.score,81.33);
  assert.equal(rows['JOURNAL COMPLETED'],1);
  assert.equal(JSON.stringify(input),before);
});

test('missing and recovered states cannot manufacture ready, balances or scores', () => {
  const rows = Object.fromEntries(exports.paperRcRows({paper_ready:'true',evidence_status:'LAST_COMMITTED_NOT_OPERATIONALLY_RESTORED'}));
  assert.equal(rows['PAPER STATUS'],'BLOCKED');
  assert.equal(rows.BALANCE,undefined);
  assert.equal(rows.CONFLUENCE,undefined);
  assert.equal(rows['EVIDENCE STATUS'],'LAST_COMMITTED_NOT_OPERATIONALLY_RESTORED');
});

test('all declared modes remain visible and only explicit PAPER mode can be ready', () => {
  for (const mode of ['PRODUCTION_POLICY','HISTORICAL_RESEARCH','PAPER_RESEARCH']) {
    const rows = Object.fromEntries(exports.paperRcRows({mode,paper_ready:true}));
    assert.equal(rows.MODE,mode);
    assert.equal(rows['PAPER STATUS'],mode==='PAPER_RESEARCH' ? 'PAPER READY' : 'BLOCKED');
  }
});
