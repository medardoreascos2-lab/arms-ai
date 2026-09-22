"""Actual R5 authored C# against synthetic doubles; never native NinjaTrader proof."""
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
from tools.verify_session_domain_probe_v1 import verify_evidence

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'integrations/ninjatrader/ArmsSessionDomainProbeV1.cs'
HARNESS = ROOT/'backend/tests/fixtures/session_domain_probe_harness_sprint16ar5.cs'
CSC = Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
SDK = Path('C:/Program Files/NinjaTrader 8/bin')


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    if not CSC.exists(): pytest.skip('Windows Framework compiler required')
    target=tmp_path_factory.mktemp('r5-probe')/'harness.exe'
    result=subprocess.run([str(CSC),'/nologo','/out:'+str(target),'/r:System.ComponentModel.DataAnnotations.dll',
        '/r:System.Web.Extensions.dll','/r:System.Core.dll',str(SOURCE),str(HARNESS)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    return target


def run(binary, folder, mode):
    folder.mkdir(exist_ok=True)
    result=subprocess.run([str(binary),mode,str(folder)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
    counts=json.loads(result.stdout)
    path=folder/'session-domain-probe.jsonl'; done=folder/'session-domain-probe.done.json'
    raw=path.read_bytes() if path.exists() else b''
    seal=done.read_bytes() if done.exists() else None
    rows=[json.loads(r) for r in raw.splitlines()]
    assert counts['native_calls']<=8 and counts['iterator_creates']<=7
    assert counts['request_invokes']<=1 and counts['request_creates']<=1
    assert counts['ninjatrader_assemblies_loaded']==0
    assert len(rows)<=96 and len(raw)<=262144
    assert b'PRIVATE_PROVIDER_SENTINEL' not in raw+result.stdout.encode()
    assert all(r['runtime_admission'] is False and r['certification_evidence'] is False for r in rows)
    assert not list(folder.glob('*.historical.jsonl'))
    return counts,rows,raw,seal


def reseal(rows, original):
    raw=b''.join(json.dumps(r,separators=(',',':')).encode()+b'\n' for r in rows)
    seal=json.loads(original); seal.update(sha256=sha256(raw).hexdigest(),records=len(rows),bytes=len(raw))
    return raw,json.dumps(seal).encode()


@pytest.mark.parametrize('mask',range(64))
def test_all_gap_next_constructor_combinations_are_descriptive_only(binary,tmp_path,mask):
    counts,rows,raw,seal=run(binary,tmp_path,'matrix_'+str(mask))
    result=verify_evidence(raw,seal)
    assert result['root_cause']=='UNRESOLVED' and result['adjudication']=='OBSERVATIONS_ONLY'
    assert counts['request_creates']==counts['request_invokes']==counts['request_disposes']==1
    assert counts['native_calls']==result['native_calls']
    assert counts['iterator_creates']==result['iterator_count']
    observations=counts['observations']
    assert all(o['same_snapshot'] and o['kind']=='Utc' for o in observations)
    if not mask&16:
        assert [(o['iterator'],o['call']) for o in observations[:2]]==[(1,1),(1,2)]
        assert len({o['iterator'] for o in observations[2:]})==len(observations)-2
    else: assert len({o['iterator'] for o in observations})==len(observations)
    assert counts['begin_reads']==counts['end_reads']==sum(r['boolean_result'] for r in rows if r['stage']=='CALL_RESULT')
    expected='FRESH_ITERATOR_SAME_RESULT' if bool(mask&1)==bool(mask&2) else 'ITERATOR_REUSE_DIFFERENCE'
    if not mask&16: assert expected in result['findings']
    else: assert 'UNRESOLVED' in result['findings']
    assert ('CONSTRUCTOR_CONTEXT_DIFFERENCE' in result['findings']) == (bool(mask&4)!=bool(mask&8))


@pytest.mark.parametrize('mode', ['maximum','with_next','before_only','noncontiguous','gap_coverage','boundary_coverage','first_false','large'])
def test_coverage_checkpoints_and_case_prerequisites(binary,tmp_path,mode):
    counts,rows,raw,seal=run(binary,tmp_path,mode)
    result=verify_evidence(raw,seal); cov=result['coverage']
    assert cov['first_kind']==cov['last_kind']=='Utc'
    assert sum(b['count'] for b in cov['utc_dates'].values())==cov['returned_rows']
    if mode=='maximum':
        assert counts['native_calls']==8 and counts['iterator_creates']==7
        assert cov['first']=='2026-09-16T12:00:00.0000000Z' and cov['last']=='2026-09-16T12:04:00.0000000Z'
        assert cov['covered_query']=='2026-09-16T12:01:00.0000000Z' and cov['covered_source_index']==1
        assert result['results']['E_TRUE']['include_end_time'] is True
        assert result['results']['E_FALSE']['include_end_time'] is False
    if mode=='before_only':
        assert cov['after_first_session_count']==0 and cov['covered_query'] is None
        assert 'C' not in result['results'] and 'SNAPSHOT_COVERAGE_FAILURE' in result['findings']
    if mode=='with_next':
        assert cov['session_bins'][1]['count']==5 and 'T_NEXT' not in result['results']
    if mode=='gap_coverage':
        assert cov['maintenance_count']==4 and cov['covered_query'] is None
    if mode=='first_false': assert 'R1' not in result['results'] and 'UNRESOLVED' in result['findings']
    if mode=='large': assert cov['returned_rows']==4503 and len(raw)<50000 and len(rows)<32
    if 'C' in result['results']:
        assert result['results']['C']['query']==cov['covered_query']
        assert result['results']['C']['source_index']==cov['covered_source_index']


@pytest.mark.parametrize('mode', ['inline','async','clone','reentrant'])
def test_inline_async_duplicate_and_reentrant_callbacks(binary,tmp_path,mode):
    counts,rows,raw,seal=run(binary,tmp_path,mode)
    verify_evidence(raw,seal)
    assert counts['request_invokes']==counts['request_disposes']==1
    assert sum(r['stage']=='EXPERIMENT_COMPLETE' for r in rows)==1


@pytest.mark.parametrize('mode', ['closed','no_flow','unstable','timezone','playback','request_throw','inline_then_throw',
    'empty','too_many','wrong_instrument','wrong_period','provider_policy','wrong_template','callback_error','wrong_callback',
    'constructor_throw','environment_changed','template_mutated','snapshot_mutated','foreign_file','changed_properties','terminated',
    'call_cap','iterator_cap','record_cap','byte_cap','template_exception','wrong_schedule','bad_order','bad_time_kind',
    'too_many_dates','advance_throw','begin_throw','end_throw','reversed_bounds','unspecified','anchor_mismatch'])
def test_fail_closed_no_seal_no_retry(binary,tmp_path,mode):
    counts,rows,raw,seal=run(binary,tmp_path,mode)
    assert seal is None
    assert counts['request_disposes']==counts['request_creates']
    assert not any(r['stage']=='EXPERIMENT_COMPLETE' for r in rows)
    if mode in ('closed','no_flow','unstable','timezone','playback'): assert counts['request_invokes']==0
    if mode in ('bad_order','bad_time_kind','template_exception','wrong_schedule','too_many_dates'): assert counts['native_calls']==0
    with pytest.raises(ValueError): verify_evidence(raw,seal)


@pytest.mark.parametrize('mode',['defaults','pending'])
def test_disabled_or_pending_never_completes(binary,tmp_path,mode):
    counts,rows,raw,seal=run(binary,tmp_path,mode)
    assert counts['native_calls']==0 and seal is None
    if mode=='defaults': assert counts['request_creates']==0 and rows==[] and list(tmp_path.iterdir())==[]


def test_existing_directory_evidence_never_overwritten(binary,tmp_path):
    run(binary,tmp_path,'maximum')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    counts,*_=run(binary,tmp_path,'maximum')
    assert counts['request_creates']==0
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before


@pytest.fixture(scope='module')
def evidence(binary,tmp_path_factory):
    _,rows,raw,seal=run(binary,tmp_path_factory.mktemp('r5-evidence'),'maximum')
    verify_evidence(raw,seal)
    return rows,raw,seal


@pytest.mark.parametrize('field,value', [('query','2026-09-14T21:00:00.0000001Z'),
    ('query_kind','Unspecified'),('include_end_time',False),('iterator_id','R'),('constructor','TradingHours'),('mode','REUSED'),
    ('native_calls',8),('iterator_count',9),('request_count',2),('maximum_native_calls',9),('case_id','R1'),
    ('source_index',1),('call_index',0),('boolean_result',True),('session_begin','2026-09-13T22:00:00.0000000Z'),
    ('guard','UNKNOWN'),('exception_type','OTHER'),('bounds_valid',True),('root_cause','MAINTENANCE_GAP'),
    ('snapshot_sha256','0'*64),('template_sha256','0'*64),('runtime_admission',True),('returned_rows',True),
    ('phase','NOT_CALLED'),('request_id','00000000-0000-0000-0000-000000000000')])
def test_resealed_call_contradictions_rejected(evidence,field,value):
    rows,_,seal=evidence; changed=deepcopy(rows)
    row=next(r for r in changed if r['stage']=='CALL_RESULT' and r['case_id']=='G')
    row[field]=value
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


@pytest.mark.parametrize('field,value',[('first',None),('last','2026-09-16T12:00:00.0000000Z'),('first_kind','Local'),
    ('covered_source_index',0),('covered_query','2026-09-17T12:01:00.0000000Z'),('covered_session',1),
    ('after_first_session_count',0),('maintenance_count',1),('outside_count',1),('strictly_ordered',False),
    ('utc_dates',{}),('session_bins',[]),('returned_rows',4503),('exact_boundary_count',True)])
def test_resealed_coverage_contradictions_rejected(evidence,field,value):
    rows,_,seal=evidence; changed=deepcopy(rows)
    next(r for r in changed if r['stage']=='COVERAGE_VERIFIED')['coverage'][field]=value
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


@pytest.mark.parametrize('fault',['remove','duplicate','swap','early_return','missing_return','duplicate_return','skip_predicate',
    'complete_early','forged_findings','extra_field','missing_coverage','template_corrupt','float_sequence','forged_adjudication'])
def test_resealed_lifecycle_and_plan_corruption(evidence,fault):
    rows,_,seal=evidence; changed=deepcopy(rows)
    if fault=='remove': changed.pop(5)
    elif fault=='duplicate': changed.insert(6,deepcopy(changed[5]))
    elif fault=='swap': changed[5],changed[6]=changed[6],changed[5]
    elif fault=='early_return':
        r=next(r for r in changed if r['stage']=='REQUEST_RETURNED');changed.remove(r);changed.insert(6,r)
    elif fault=='missing_return': changed=[r for r in changed if r['stage']!='REQUEST_RETURNED']
    elif fault=='duplicate_return': changed.insert(2,deepcopy(changed[2]))
    elif fault=='skip_predicate': next(r for r in changed if r['case_id']=='E_FALSE')['stage']='CASE_SKIPPED'
    elif fault=='complete_early': changed[4]['stage']='EXPERIMENT_COMPLETE'
    elif fault=='forged_findings': changed[-1]['findings']=['MAINTENANCE_GAP_CAUSE_PROVEN']
    elif fault=='extra_field': changed[-1]['unknown']=1
    elif fault=='missing_coverage': next(r for r in changed if r['stage']=='COVERAGE_VERIFIED')['coverage']=None
    elif fault=='template_corrupt': next(r for r in changed if r['stage']=='SNAPSHOT_VERIFIED')['template_payload']='{}'
    elif fault=='forged_adjudication': changed[-1]['adjudication']='PASS'
    for i,r in enumerate(changed): r['sequence']=i
    if fault=='float_sequence': changed[-1]['sequence']=float(len(changed)-1)
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


@pytest.mark.parametrize('fault',['hash','count','bytes','uuid','calls','iterators','requests','findings','complete','schema',
    'truncated','newline','empty','oversize','duplicate_json_key','non_json'])
def test_seal_and_malformed_input_fail_closed(evidence,fault):
    _,raw,original=evidence; seal=json.loads(original)
    fields={'hash':('sha256','0'*64),'count':('records',1),'bytes':('bytes',1),'uuid':('probe_uuid','bad'),
        'calls':('native_calls',9),'iterators':('iterator_count',8),'requests':('request_count',2),
        'findings':('findings',[]),'complete':('diagnostic_complete',False),'schema':('schema','other')}
    if fault in fields: k,v=fields[fault];seal[k]=v
    elif fault=='truncated': raw=raw[:len(raw)//2]
    elif fault=='newline': raw=raw[:-1]
    elif fault=='empty': raw=b''
    elif fault=='oversize': raw=b'x'*262145
    elif fault=='non_json': raw=b'{invalid}\n'
    encoded=json.dumps(seal).encode()
    if fault=='duplicate_json_key': encoded=encoded[:-1]+b',"request_count":1}'
    with pytest.raises(ValueError): verify_evidence(raw,encoded)


@pytest.mark.parametrize('value',[None,[],{},True,1,1.0,''])
def test_invalid_top_level_types(evidence,value):
    rows,raw,seal=evidence
    with pytest.raises(ValueError): verify_evidence(value,seal)
    with pytest.raises(ValueError): verify_evidence(raw,value)


def test_verifier_cli_and_history_rejection(evidence,tmp_path):
    from backend.market_data.certified_bootstrap_v1 import certify_bootstrap
    _,raw,seal=evidence
    with pytest.raises(ValueError): certify_bootstrap(raw,expected_sha256=sha256(raw).hexdigest())
    path=tmp_path/'probe.jsonl'; done=tmp_path/'done.json';path.write_bytes(raw);done.write_bytes(seal)
    cmd=[sys.executable,'-B',str(ROOT/'tools/verify_session_domain_probe_v1.py'),'--diagnostic',str(path),'--seal',str(done)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert result.returncode==0 and json.loads(result.stdout)['root_cause']=='UNRESOLVED'
    cmd[-1]=str(tmp_path/'missing')
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
    assert result.returncode==1 and result.stderr=='' and json.loads(result.stdout)['diagnostic_integrity']=='REJECTED'


def test_structural_safety_and_preserved_components():
    source=re.sub(r'//[^\n]*','',SOURCE.read_text())
    source=re.sub(r'\[Display\([^\n]*\)\]','',source)
    assert not re.search(r'\b(Account|Order|Execution|SubmitOrder|CreateOrder|AtmStrategy|Process|Timer|DllImport|Activator)\b',source)
    assert not re.search(r'\.(Update|Connect|Disconnect)\s*[+=(]',source)
    assert re.findall(r'Connection\.(\w+)',source)==['PlaybackConnection']
    assert source.count('new BarsRequest(')==source.count('request.Request(')==1
    assert source.count('iterator.GetNextSession(')==1
    for name in ('ArmsHistoricalBootstrapV1.cs','ArmsReadOnlyMarketV1.cs','ArmsSessionIteratorProbeV1.cs'):
        path='integrations/ninjatrader/'+name
        baseline=subprocess.check_output(['git','show','c24f225cf3984f020e49979b10077a4739bb588c:'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes().replace(b'\r\n',b'\n')==baseline.replace(b'\r\n',b'\n')


def test_installed_sdk_compile(tmp_path):
    if not CSC.exists() or not (SDK/'NinjaTrader.Core.dll').exists(): pytest.skip('Installed Windows SDK required')
    shim=tmp_path/'Indicator.cs'
    shim.write_text('namespace NinjaTrader.NinjaScript.Indicators { public class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase {} }')
    refs=[SDK/'NinjaTrader.Core.dll',SDK/'NinjaTrader.Gui.dll',CSC.parent/'WPF/WindowsBase.dll',
        'System.ComponentModel.DataAnnotations.dll','System.Web.Extensions.dll','System.Core.dll']
    result=subprocess.run([str(CSC),'/nologo','/target:library','/out:'+str(tmp_path/'Probe.dll'),
        *['/r:'+str(p) for p in refs],str(SOURCE),str(shim)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr


def test_installed_template_encoding_and_payload_fit_reviewed_contract():
    """Disk XML only: checks HHmm units and bound size, not the future loaded instance."""
    import xml.etree.ElementTree as ET
    from tools.verify_session_domain_probe_v1 import template
    path=Path(os.environ['USERPROFILE'])/'OneDrive/Documents/NinjaTrader 8/templates/TradingHours/CME US Index Futures ETH.xml'
    if not path.exists(): pytest.skip('Installed template required')
    root=ET.fromstring(path.read_bytes()).find('TradingHours')
    days=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    def session(s):
        return ','.join([str(days.index(s.findtext('BeginDay'))),s.findtext('BeginTime'),
            str(days.index(s.findtext('EndDay'))),s.findtext('EndTime'),str(days.index(s.findtext('TradingDay')))])
    data=dict(sessions=[session(s) for s in root.find('Sessions')],
        holidays=sorted(h.findtext('Date')[:10] for h in root.find('HolidaysSerializable')),partials=[])
    for h in root.find('PartialHolidaysSerializable'):
        data['partials'].append('|'.join([h.findtext('Date')[:10],
            '1' if h.findtext('IsEarlyEnd')=='true' else '0','1' if h.findtext('IsLateBegin')=='true' else '0',
            session(h.find('Constraint')) if h.find('Constraint') is not None else 'NONE',
            ';'.join(session(s) for s in h.find('Sessions'))]))
    data['partials'].sort()
    raw=json.dumps(data,separators=(',',':'))
    template(raw,sha256(raw.encode()).hexdigest())
    assert len(raw.encode()) <= 10000
    source=SOURCE.read_text()
    assert all('"'+s+'"' in source for s in data['sessions'])


@pytest.mark.parametrize('fault',['post_checkpoint','gap_checkpoint','boundary_checkpoint','candidate_omission','date_count',
    'session_index','date_index','session_time','duplicate_boundary','float_bucket_count'])
def test_coverage_checkpoint_graph_cannot_be_resealed_into_consistency(evidence,fault):
    rows,_,seal=evidence; changed=deepcopy(rows)
    cov=next(r for r in changed if r['stage']=='COVERAGE_VERIFIED')['coverage']
    if fault=='post_checkpoint': cov['post_first']['first_index']=1
    elif fault=='gap_checkpoint': cov['maintenance_bins'][0]['count']=1
    elif fault=='boundary_checkpoint': cov['exact_boundary_count']=1
    elif fault=='candidate_omission': cov['session_bins'][cov['covered_session']]['candidate_index']=-1; cov['session_bins'][cov['covered_session']]['candidate']=None
    elif fault=='date_count': next(iter(cov['utc_dates'].values()))['count']=4
    elif fault=='session_index': cov['session_bins'][cov['covered_session']]['last_index']=3
    elif fault=='date_index': next(iter(cov['utc_dates'].values()))['first_index']=1
    elif fault=='session_time': cov['session_bins'][cov['covered_session']]['first']='2026-09-16T12:01:00.0000000Z'
    elif fault=='duplicate_boundary': cov['boundary_points']=[{'index':0,'time':cov['first']}]*2
    else: cov['session_bins'][cov['covered_session']]['count']=5.0
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))


def test_impossible_minute_density_rejected_even_if_all_summary_indices_agree(evidence):
    rows,_,seal=evidence; changed=deepcopy(rows)
    # Stretch every index after the C checkpoint, with matching counts throughout.
    # The altered six-row snapshot still spans only five available minute labels.
    for row in changed:
        if row['returned_rows']==5: row['returned_rows']=6
    cov=next(r for r in changed if r['stage']=='COVERAGE_VERIFIED')['coverage']
    cov['returned_rows']=cov['after_first_session_count']=6
    cov['post_first']['count']=6; cov['post_first']['last_index']=5
    for bucket in list(cov['utc_dates'].values())+cov['session_bins']:
        if bucket['count']==5: bucket['count']=6; bucket['last_index']=5
    with pytest.raises(ValueError): verify_evidence(*reseal(changed,seal))
