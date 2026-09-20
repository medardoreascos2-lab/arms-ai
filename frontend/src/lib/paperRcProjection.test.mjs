import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./paperRcProjection.ts', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, { exports });

test('session and provider are independent projections; missing SIM authority is not enabled', () => {
  const input = {session_state:{state:'WEEKEND_CLOSED',reason:'WEEKEND_CLOSED'},
    provider_state:'CONNECTED',data_freshness:'STALE_OR_MISSING',sim_execution_authority:'DISABLED',
    sim_eligibility_status:'UNKNOWN_ACCOUNT_INELIGIBLE'};
  const before = JSON.stringify(input);
  const rows = Object.fromEntries(exports.currentPaperRows(input));
  assert.equal(rows['MARKET SESSION STATE'],'WEEKEND_CLOSED');
  assert.equal(rows['PROVIDER STATE'],'CONNECTED');
  assert.equal(rows['SIM EXECUTION AUTHORITY'],'DISABLED');
  assert.equal(rows['PAPER STATUS'],'BLOCKED');
  assert.equal(Object.fromEntries(exports.currentPaperRows({}))['SIM EXECUTION AUTHORITY'],undefined);
  assert.equal(JSON.stringify(input),before);
});

test('SIM discovery projects safe status fields without account identifiers', () => {
  const input = {sim_discovery_status:'NOT_IMPLEMENTED_AUTHORITY_UNPROVEN',
    sim_classification_status:'UNKNOWN',sim_binding_status:'NOT_CONFIGURED',sim_execution_authority:'DISABLED',
    account_id:'SYNTHETIC_PRIVATE_IDENTIFIER'};
  const rows = Object.fromEntries(exports.currentPaperRows(input));
  assert.equal(rows['SIM CLASSIFICATION STATUS'],'UNKNOWN');
  assert.equal(rows['SIM BINDING STATUS'],'NOT_CONFIGURED');
  assert.equal(rows['SIM DISCOVERY STATUS'],'NOT_IMPLEMENTED_AUTHORITY_UNPROVEN');
  assert.equal(rows['SIM EXECUTION AUTHORITY'],'DISABLED');
  assert.equal(JSON.stringify(rows).includes('SYNTHETIC_PRIVATE_IDENTIFIER'),false);
});

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

test('current feed projection preserves canonical values and separates replay readiness', () => {
  const input = {mode:'CURRENT_MARKET_PAPER',paper_ready:true,execution_kind:'SIMULATED / PAPER',
    market_data:{provider:'FIXTURE',contract:'NQ TEST',connected:true,data_age_seconds:2,version:4},
    account_overview:{balance:150540},recovery_required:false};
  const before = JSON.stringify(input);
  const rows = Object.fromEntries(exports.currentPaperRows(input));
  assert.equal(rows['PAPER STATUS'],'PAPER READY');
  assert.equal(rows['CURRENT CONTRACT'],'NQ TEST');
  assert.equal(rows['DATA AGE SECONDS'],2);
  assert.equal(rows.BALANCE,150540);
  assert.equal(Object.fromEntries(exports.paperRcRows(input))['PAPER STATUS'],'BLOCKED');
  assert.equal(Object.fromEntries(exports.currentPaperRows({...input,paper_ready:false}))['PAPER STATUS'],'BLOCKED');
  assert.equal(Object.fromEntries(exports.currentPaperRows({mode:'PAPER_RESEARCH',paper_ready:true}))['PAPER STATUS'],'BLOCKED');
  assert.equal(JSON.stringify(input),before);
});
