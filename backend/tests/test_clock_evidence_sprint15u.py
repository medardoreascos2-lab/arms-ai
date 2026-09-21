"""Synthetic packet/callback fixtures; never Windows changes or native capture."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
from types import SimpleNamespace

import pytest

from tools import clock_evidence_v1 as evidence
from tools.clock_preflight_v1 import Interval, assess
from backend.tests.test_clock_preflight_sprint15t import fixture_inputs


BASE = 1_790_000_040_000_000_000  # Integer ns, aligned minute.
REF = "time.cloudflare.com"


def packet_case(offset=0, delay=2_000_000):
    sent = dict(host_ns=BASE-offset,mono_before_ns=10_000_000,mono_after_ns=10_000_100)
    received = dict(host_ns=BASE+delay-offset,mono_before_ns=10_000_000+delay,
                    mono_after_ns=10_000_100+delay)
    raw = bytearray(48)
    raw[0], raw[1], raw[3] = 0x24, 2, 236
    origin = evidence.encode_time(sent['host_ns'])
    raw[24:32] = origin
    raw[32:40] = evidence.encode_time(BASE+delay//2)
    raw[40:48] = raw[32:40]
    return raw, origin, sent, received


@pytest.mark.parametrize('offset',[0,-1_000_000_000,-150_000_000,-10_000_000,10_000_000,150_000_000,1_000_000_000])
def test_exact_leading_lagging_packet_has_measurement_not_authority(offset):
    row = evidence.decode_reply(*packet_case(offset),REF,'capture')
    assert abs(row['midpoint_offset_ns']-offset)<=1
    assert row['origin_echo_matched'] and not row['authenticated']
    assert row['reviewed_reference_error_us'] is None
    assert row['reviewed_rate_error_ppb'] is None
    assert row['conditional_receipt_utc_ns'][0] <= BASE+2_000_000 <= row['conditional_receipt_utc_ns'][1]


@pytest.mark.parametrize('attack',['short','extension','client','version','unsynced','leap',
                                  'kod','stratum','origin','zero','reversed_reference',
                                  'reversed_wall','reversed_mono','pair','oversized_duration'])
def test_invalid_reply_cannot_become_sample(attack):
    raw, origin, sent, received = packet_case()
    if attack=='short': raw=raw[:-1]
    if attack=='extension': raw+=b'extension'
    if attack=='client': raw[0]=0x23
    if attack=='version': raw[0]=0x14
    if attack=='unsynced': raw[0]|=0xc0
    if attack=='leap': raw[0]|=0x40
    if attack=='kod': raw[1]=0
    if attack=='stratum': raw[1]=16
    if attack=='origin': raw[24]^=1
    if attack=='zero': raw[32:40]=bytes(8)
    if attack=='reversed_reference': raw[40:48]=evidence.encode_time(BASE)
    if attack=='reversed_wall': received['host_ns']=sent['host_ns']-1
    if attack=='reversed_mono': received['mono_before_ns']=1
    if attack=='pair': sent['mono_after_ns']=sent['mono_before_ns']-1
    if attack=='oversized_duration': raw[40:48]=evidence.encode_time(BASE+10_000_000)
    with pytest.raises(ValueError): evidence.decode_reply(raw,origin,sent,received,REF,'capture')


def test_high_roundtrip_widens_enclosure_not_accuracy():
    normal=evidence.decode_reply(*packet_case(),REF,'capture')
    delayed=evidence.decode_reply(*packet_case(delay=500_000_000),REF,'capture')
    assert delayed['conditional_asymmetry_radius_ns']>normal['conditional_asymmetry_radius_ns']
    now=dict(mono_before_ns=600_000_000)
    report=evidence.summarize([normal,delayed],now)
    assert report['references'][REF]['count']==2
    assert report['references'][REF]['roundtrip_range_ns'][1]==500_000_100
    assert report['absolute_uncertainty_status']=='UNKNOWN'


def test_delay_asymmetry_never_assumed_zero():
    raw,origin,sent,received=packet_case()
    for reference_time in (BASE,BASE+2_000_000):
        raw[32:40]=raw[40:48]=evidence.encode_time(reference_time)
        row=evidence.decode_reply(raw,origin,sent,received,REF,'capture')
        assert row['conditional_receipt_utc_ns'][0]<=BASE+2_000_000<=row['conditional_receipt_utc_ns'][1]
        assert row['conditional_asymmetry_radius_ns']>=1_000_000


@pytest.mark.parametrize('attack',['disagree','stale','host_drift','restart'])
def test_existing_preflight_rejects_changed_acquisition_evidence(attack):
    x=fixture_inputs()
    s=x['samples'][-1]
    if attack=='disagree': s=replace(s,reference_receive_us=s.reference_receive_us+1000,reference_send_us=s.reference_send_us+1000)
    if attack=='stale': s=replace(s,mono_send_us=-1)
    if attack=='host_drift': s=replace(s,host_receive_us=s.host_receive_us+1000)
    if attack=='restart': s=replace(s,epoch='new-process')
    x['samples']=(*x['samples'][:-1],s)
    result=assess(**x)
    assert result['status']=='UNKNOWN'
    assert not any(result['clock_ready'].values())
    assert result['broker_order_calls']==0 and not result['execution_authority']


def test_empirical_drift_is_not_promoted_to_rate_bound():
    first=evidence.decode_reply(*packet_case(),REF,'capture')
    last=deepcopy(first)
    last['received']['host_ns']+=5_000_200_000
    last['received']['mono_after_ns']+=5_000_000_000
    last['midpoint_offset_ns']-=200_000
    report=evidence.summarize([first,last],dict(mono_before_ns=6_000_000_000))
    r=report['references'][REF]
    assert r['observed_host_mono_rate_ppb']==40_000
    assert r['observed_offset_slope_ppb']==-40_000
    assert r['reviewed_rate_bound_ppb'] is None


def candidate(kind='CLOSED',margin=150_000):
    close=BASE//1000
    boundary=close-(60_000_000 if kind=='FORMING' else 0)
    record=dict(epoch='capture',native_session='native',calendar_sha256='reviewed-calendar',
                state='Realtime',connection_continuity=True,callback_bound_to_exporter_record=True,
                source=['Provider31','NQ DEC26','Minute',1,'UTC','CME US Index Futures ETH'],
                kind=kind,close_label_us=close)
    window=evidence.analysis_window(kind,close,30_000_000,close-3_600_000_000,close+3_600_000_000,'SYNTHETIC')
    return dict(record=record,epoch='capture',native_session='native',calendar_hash='reviewed-calendar',
                window=window,event_utc=Interval(boundary+margin,boundary+margin+10),
                receipt_utc=Interval(boundary+margin+20,boundary+margin+30),
                now_utc=Interval(boundary+margin+40,boundary+margin+50),maximum_age_us=30_000_000)


@pytest.mark.parametrize('kind',['FORMING','CLOSED'])
@pytest.mark.parametrize('margin',[-150_000,-1,0,1,50_000,150_000,1_000_000])
def test_native_boundary_proof_is_per_record_not_fixed_offset_gate(kind,margin):
    x=candidate(kind,margin)
    result=evidence.native_candidate_proof(**x)
    assert result==('UNKNOWN' if margin<0 else 'PROVEN_TIME_CONDITIONS_ONLY')


@pytest.mark.parametrize('attack',['restart','reconnect','historical','session','sibling_callback',
                                  'wrong_source','future','stale','clock_overlap','missing','bad_label'])
def test_native_identity_freshness_and_lifecycle_fail_closed(attack):
    x=candidate()
    if attack=='restart': x['record']['epoch']='another'
    if attack=='reconnect': x['record']['connection_continuity']=False
    if attack=='historical': x['record']['state']='Historical'
    if attack=='session': x['record']['calendar_sha256']='another'
    if attack=='sibling_callback': x['record']['callback_bound_to_exporter_record']=False
    if attack=='wrong_source': x['record']['source'][0]='UNKNOWN'
    if attack=='future': x['event_utc']=Interval(BASE//1000-1,BASE//1000+10)
    if attack=='stale': x['now_utc']=Interval(BASE//1000+30_000_001,BASE//1000+30_000_002)
    if attack=='clock_overlap': x['receipt_utc']=x['event_utc']
    if attack=='missing': del x['record']['native_session']
    if attack=='bad_label': x['record']['close_label_us']+=1
    assert evidence.native_candidate_proof(**x)=='UNKNOWN'


def test_waiting_does_not_repair_a_future_emission():
    x=candidate(margin=-1)
    close=BASE//1000
    x['receipt_utc']=Interval(close+100,close+110)
    for delta in (1000,1_000_000,29_000_000,31_000_000):
        x['now_utc']=Interval(close+delta,close+delta+10)
        assert evidence.native_candidate_proof(**x)=='UNKNOWN'


def test_session_end_excluded_even_while_candle_fresh():
    x=candidate()
    close=BASE//1000
    x['window']=evidence.analysis_window('CLOSED',close,30_000_000,close-60_000_000,close+1000,'SYNTHETIC')
    x['event_utc']=Interval(close,close)
    x['receipt_utc']=Interval(close+100,close+100)
    x['now_utc']=Interval(close+999,close+1000)
    assert evidence.native_candidate_proof(**x)=='UNKNOWN'
    x['now_utc']=Interval(close+999,close+999)
    assert evidence.native_candidate_proof(**x)=='PROVEN_TIME_CONDITIONS_ONLY'


@pytest.mark.parametrize('change',[{'kind':'UNKNOWN'},{'close_us':1},{'freshness_us':0},
                                    {'session_start_us':BASE//1000},{'provenance':''}])
def test_no_fabricated_or_unreviewed_window(change):
    x=dict(kind='CLOSED',close_us=BASE//1000,freshness_us=30_000_000,
           session_start_us=BASE//1000-60_000_000,session_end_us=BASE//1000+60_000_000,provenance='SYNTHETIC')
    x.update(change)
    with pytest.raises(ValueError): evidence.analysis_window(**x)


def test_collection_is_bounded_and_cannot_grant_any_authority(monkeypatch):
    calls=[]
    monkeypatch.setattr(evidence,'windows_snapshot',lambda:{'last_sync_mono_us':None})
    monkeypatch.setattr(evidence,'clock_rate',lambda:{'status':'SYNTHETIC'})
    monkeypatch.setattr(evidence,'resolve',lambda r:'192.0.2.1')
    monkeypatch.setattr(evidence.time,'sleep',lambda seconds:calls.append(seconds))
    def fake(reference,address,epoch):
        return evidence.decode_reply(*packet_case(),reference,epoch)
    monkeypatch.setattr(evidence,'probe',fake)
    result=evidence.collect(rounds=2,period=1)
    assert len(result['records'])==6 and len(result['rates'])==2
    assert all(0<s<=1 for s in calls)
    assert result['preflight']['status']=='UNKNOWN'
    assert not any(result['preflight']['clock_ready'].values())
    assert not result['watcher_armed'] and not result['windows_changed']
    assert not result['preflight']['account_access'] and result['preflight']['broker_order_calls']==0
    assert result['paper_entries']=='DISABLED' and result['news']=='UNCERTIFIED'


@pytest.mark.parametrize('rounds,period',[(1,5),(13,5),(2,0),(12,6),(True,1)])
def test_unbounded_or_undersampled_configuration_rejected(rounds,period):
    with pytest.raises(ValueError): evidence.collect(rounds,period)


def test_windows_commands_are_read_only_and_preserve_sync_mapping_unknown(monkeypatch):
    calls=[]
    monkeypatch.setattr(evidence,'os',SimpleNamespace(name='nt'))
    def run(command,**kwargs):
        calls.append(command)
        assert kwargs['timeout']==5
        return SimpleNamespace(returncode=0,stdout='synthetic output')
    monkeypatch.setattr(evidence.subprocess,'run',run)
    result=evidence.windows_snapshot()
    assert all(c[:2]==['w32tm','/query'] for c in calls[:3])
    assert 'Get-CimInstance Win32_Service' in calls[3][-1]
    assert result['last_sync_mono_us'] is None


def test_exclusive_output_refuses_old_evidence(tmp_path,monkeypatch):
    p=tmp_path/'existing.json'
    p.write_text('preserve')
    monkeypatch.setattr(evidence.sys,'argv',['clock_evidence','--output',str(p)])
    monkeypatch.setattr(evidence,'collect',lambda:pytest.fail('must not probe'))
    with pytest.raises(FileExistsError): evidence.main()
    assert p.read_text()=='preserve'


def test_contract_preserves_unresolved_bounds_and_disabled_operations():
    path=Path(__file__).with_name('clock_evidence_sprint15u.json')
    contract=json.loads(path.read_text())
    assert contract['reviewed_bounds'] is None
    assert contract['native_capture']['armed'] is False
    assert contract['native_capture']['exporter_modified'] is False
    assert all(value=='UNKNOWN_INELIGIBLE' for value in contract['clock_readiness'].values())
