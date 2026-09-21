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
test('adapter lifecycle cannot project bootstrap, waiting, disconnected or revoked data as LIVE',()=>{
  for (const mode of ['WAITING','BOOTSTRAP','DISCONNECTED','REVOKED']) {
    const source={...healthy(),adapter_status:mode,stream_mode:mode,exporter_session_status:'BOUND',timing_pair_status:'EXACT_PREFIX',order_submit_reachable:false};
    const r=project(source);assert.equal(r.ADAPTER_STATUS,mode);assert.equal(r.MARKET_STREAM,'NOT_LIVE');
    assert.equal(r['1M'],'BLOCKED / INSUFFICIENT DATA');
  }
  const source={...healthy(),adapter_status:'LIVE_TAIL',stream_mode:'LIVE_TAIL',exporter_session_status:'BOUND',timing_pair_status:'EXACT_PREFIX',order_submit_reachable:false,canonical_sequence:123};
  const r=project(source);assert.equal(r.TRANSPORT_STATUS,'TRANSPORT_LIVE');assert.equal(r.CANONICAL_SEQUENCE,123);
  assert.equal(r.ABSOLUTE_MARKET_RECENCY,'UNKNOWN');assert.equal(r.PROCESSING_AGE_STATUS,'QPC_OBSERVED');
  source.timing_pair_status='WAITING';assert.equal(project(source).MARKET_STREAM,'NOT_LIVE');
});

const historical = () => ({...healthy(),market_stream:'NOT_LIVE',analysis_status:'BLOCKED',
  transport_liveness:'UNKNOWN_OR_LOST',canonical_continuity:'UNPROVEN_OR_REVOKED',
  processing_age:{status:'UNKNOWN',seconds:null},bootstrap_status:'CERTIFIED_BOOTSTRAP',
  bootstrap_source:'SEALED_NATIVE_PRODUCTION',bootstrap_sha256:'a'.repeat(64),bootstrap_bar_count:3000,
  bootstrap_cutoff:'2026-09-21T14:00:00.0000000Z',bootstrap_gap_count:2,live_handoff_status:'AWAITING_LIVE_TAIL',
  complete_buckets:{'1h':{count:50,latest_complete_label:'2026-09-21T08:00:00-05:00',label_convention:'OPEN'}},
  components:{'1h':{status:'CERTIFIED_BOOTSTRAP_ONLY',data_class:'CERTIFIED_BOOTSTRAP',value:{close:20000,source_open:'2026-09-21T08:00:00-05:00'}},
    trend_1h:{status:'CERTIFIED_BOOTSTRAP_ONLY',data_class:'CERTIFIED_BOOTSTRAP',value:{direction:'BULLISH',confidence:1}}}});

test('certified initialization is visible without promoting liveness or execution',()=>{
  const r=project(historical());
  assert.equal(r.MARKET_STREAM,'NOT_LIVE');assert.equal(r.ANALYSIS_STATUS,'BLOCKED');
  assert.equal(r['1H'].status,'CERTIFIED_BOOTSTRAP_ONLY');assert.equal(r.TREND_1H.direction,'BULLISH');
  assert.equal(r.TREND_1H.confidence,undefined);assert.equal(r.CONFIDENCE,'NOT_PROJECTED');
  assert.equal(r['1H_COMPLETE_BUCKET_COUNT'],50);assert.equal(r.BOOTSTRAP_BAR_COUNT,3000);
  assert.equal(r.ABSOLUTE_MARKET_RECENCY,'UNKNOWN');assert.equal(r.NEWS_AUTHORITY,'UNCERTIFIED');
  assert.equal(r.PAPER_ENTRY_AUTHORITY,'DISABLED');assert.equal(r.SIM_EXECUTION_AUTHORITY,'DISABLED');
});

test('corruption, revoked handoff, unknown origin and unsafe authority suppress bootstrap',()=>{
  for(const patch of [{fault:'TRANSPORT_LOSS'},{bootstrap_status:'UNTRUSTED_HISTORY'},
    {bootstrap_sha256:'unreviewed'},{bootstrap_source:'CSV'},{live_handoff_status:'REVOKED'},
    {adapter_status:'REVOKED'},{live_authority:true},{bootstrap_cutoff:'PRIVATE'}]) {
    const r=project({...historical(),...patch});
    assert.equal(r['1H'],'BLOCKED / INSUFFICIENT DATA');assert.equal(r.BOOTSTRAP_BAR_COUNT,0);
    assert.equal(r.MARKET_STREAM,'NOT_LIVE');
  }
  const s=historical();s.components['1h'].data_class='LIVE_TAIL';
  assert.equal(project(s)['1H'],'BLOCKED / INSUFFICIENT DATA');
});

test('healthy live receipts do not relabel initialized hourly analysis as new live values',()=>{
  const s={...healthy(),...historical(),market_stream:'LIVE',transport_liveness:'OBSERVED_RECEIPTS',
    canonical_continuity:'CONTIGUOUS_OBSERVED',processing_age:{status:'QPC_OBSERVED',seconds:1},live_handoff_status:'COMPLETE'};
  const r=project(s);assert.equal(r.MARKET_STREAM,'LIVE');assert.equal(r['1H'].status,'CERTIFIED_BOOTSTRAP_ONLY');
  assert.equal(r.REGIME,'NOT_PROJECTED');assert.equal(r.CONFLUENCE,'NOT_PROJECTED');assert.equal(r.DECISION_STATUS,'NOT_PROJECTED');
});
