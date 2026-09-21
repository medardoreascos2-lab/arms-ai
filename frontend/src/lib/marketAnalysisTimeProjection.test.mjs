import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const exports = {};
vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL('./marketAnalysisTimeProjection.ts',import.meta.url),'utf8'),
  {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports});
const healthy = () => ({schema:'arms.market-analysis-time-profile.v1',profile:'MARKET_ANALYSIS_TIME_PROFILE',
  execution_mode:'LOCAL_PAPER',paper_entry_authority:'DISABLED',sim_execution_authority:'DISABLED',live_authority:false,
  ninjatrader_account_access:false,broker_order_calls:0,paper_trades_opened:0,absolute_time_authority:'UNKNOWN',
  absolute_market_recency:'UNKNOWN',source_time_recency:'UNKNOWN',session_authority:'UNKNOWN',session_status:'UNKNOWN',
  news_authority:'UNCERTIFIED',decision_status:'NOT_PROJECTED',data_freshness:'NOT_ASSERTED',market_stream:'LIVE',fault:null,
  transport_liveness:'OBSERVED_RECEIPTS',canonical_continuity:'CONTIGUOUS_OBSERVED',processing_age:{status:'QPC_OBSERVED',seconds:.01},
  source_time_status:'LABELS_AND_RELATIVE_PROGRESS_ONLY',analysis_status:'SOURCE_RELATIVE_ONLY',components:{
    '1m':{status:'SOURCE_RELATIVE_ONLY',value:{close:20000,source_open:'2026-09-21T14:00:00+00:00',account_id:'PRIVATE'}}}});
const project = x => Object.fromEntries(exports.analysisTimeRows(x));

test('local LIVE observations never imply absolute freshness or execution readiness',()=>{
  const source=healthy(),before=JSON.stringify(source),r=project(source);
  assert.equal(r.MARKET_STREAM,'LIVE');assert.equal(r.ANALYSIS_STATUS,'SOURCE_RELATIVE_ONLY');
  assert.equal(r.ABSOLUTE_MARKET_RECENCY,'UNKNOWN');assert.equal(r.SESSION_STATUS,'UNKNOWN');
  assert.equal(r.PAPER_ENTRY_AUTHORITY,'DISABLED');assert.equal(r.LIVE_AUTHORITY,'NO');
  assert.equal(r.CONFIDENCE,'NOT_PROJECTED');assert.equal(r['1M'].close,20000);
  assert.equal(JSON.stringify(r).includes('PRIVATE'),false);assert.equal(JSON.stringify(source),before);
});
test('missing, stale, malformed, or execution-enabled responses cannot project live analysis',()=>{
  for(const source of [null,{}, {...healthy(),live_authority:true},{...healthy(),session_status:'OPEN'},
    {...healthy(),absolute_market_recency:'FRESH'},{...healthy(),fault:'lost'},
    {...healthy(),processing_age:{status:'QPC_OBSERVED',seconds:NaN}},
    {...healthy(),canonical_continuity:'UNPROVEN_OR_REVOKED'}]) {
    const r=project(source);assert.equal(r.MARKET_STREAM,'NOT_LIVE');assert.equal(r.ANALYSIS_STATUS,'BLOCKED');
    assert.equal(r['1M'],'BLOCKED / INSUFFICIENT DATA');
  }
});
test('blocked component values and unreviewed strings never leak through projection',()=>{
  const source=healthy();source.components['1m'].status='BLOCKED';
  source.components.trend={status:'SOURCE_RELATIVE_ONLY',value:{direction:'PRIVATE',confidence:1}};
  const r=project(source);assert.equal(r['1M'],'BLOCKED / INSUFFICIENT DATA');
  assert.equal(r.TREND,'BLOCKED / INSUFFICIENT DATA');assert.equal(JSON.stringify(r).includes('PRIVATE'),false);
});
test('FVG projects existing engine fields without inventing a confidence score',()=>{
  const source=healthy();source.components.fvg={status:'SOURCE_RELATIVE_ONLY',value:{fvg:true,direction:'BULLISH',gap_low:20000,gap_high:20001,gap_size:1,confidence:1}};
  const r=project(source);assert.equal(r.FVG.fvg,true);assert.equal(r.FVG.direction,'BULLISH');
  assert.equal(r.FVG.confidence,undefined);assert.equal(r.CONFIDENCE,'NOT_PROJECTED');
});
test('page polls only read endpoint, clears errors and visibility changes, expires snapshots and aborts on unmount',()=>{
  const source=fs.readFileSync(new URL('../app/market-analysis/page.tsx',import.meta.url),'utf8');
  assert.equal((source.match(/requestJson\(/g)||[]).length,1);
  assert.ok(source.includes('requestJson("/api/v2/market-analysis/time-profile", undefined, false, false, request.signal)'));
  for(const text of ['catch { clear(); }','setTimeout(clear, 2000)','"visibilitychange", clear','pending?.abort()']) assert.ok(source.includes(text));
  assert.equal(/<button|submit|\/control|account_id/.test(source),false);
});
