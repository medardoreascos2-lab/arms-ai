"""Offline synthetic fault matrix plus read-only adjudication of archived native bytes.

Synthetic input proves implementation behavior, never native acquisition/authority.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.api.market_analysis_time_app_v1 import create_market_analysis_time_app_v1
from backend.market_data.certified_bootstrap_v1 import certify_bootstrap, SCHEMA, HELLO
from backend.market_data.exporter_identity_v1 import AUTHORED_SHA256
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1
from backend.tests.test_analysis_time_sprint15x import (
    Stream, encode, stamp, ticks, assert_disabled, forbid_account_and_execution_construction,
)
from backend.tests.test_analysis_startup_sprint15yr1 import Harness

EXPORTER = Path('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs').resolve()


class Archive(Stream):
    def send(self, kind, payload, pair=None):
        if not hasattr(self, 'rows'): self.rows, self.pairs = [], []
        row = dict(schema='arms.nt.market.v1', session=self.profile.session, sequence=self.seq,
                   event_time=pair['emission']['utc'] if pair else '2026-09-21T14:00:00.0000000Z',
                   kind=kind, payload=payload)
        raw = encode(row)
        self.rows.append(row)
        if pair:
            pair['canonical_sha256'] = sha256(raw).hexdigest()
            self.pairs.append(deepcopy(pair))
        self.seq += 1
        return raw, encode(pair) if pair else None


def pack(rows, pairs):
    rawrows = [encode(row) for row in rows]
    for p in pairs:
        p['canonical_sha256'] = sha256(rawrows[p['canonical_sequence']]).hexdigest()
    canonical = b'\n'.join(rawrows)+b'\n'
    timing = b'\n'.join(encode(p) for p in pairs)+b'\n'
    seal = dict(schema='arms.nt.production-timing.seal.v1', session=rows[0]['session'],
                records=len(pairs), bytes=len(timing), sha256=sha256(timing).hexdigest(),
                canonical_records=len(rows), canonical_writer_closed=True, timing_writer_closed=True, complete=True)
    return dict(canonical_utf8=canonical.decode(), timing_utf8=timing.decode(), seal_utf8=encode(seal).decode())


def segment(count, *, shift=0):
    s = Archive()
    for _ in range(count+2): s.boundary()
    s.send('DISCONNECTED', dict(connected=False, reason='TERMINATED', error_code='NONE'))
    def shifted(label):
        return stamp(datetime.fromisoformat(label.replace('Z','+00:00'))+timedelta(minutes=shift))
    session = str(uuid4())
    for row in s.rows:
        row['session'] = session
        row['event_time'] = shifted(row['event_time'])
        if row['kind'] in ('CLOSED','FORMING'): row['payload']['bar_time'] = shifted(row['payload']['bar_time'])
    for p in s.pairs:
        p['session'] = session
        p['source_bar_label'] = shifted(p['source_bar_label'])
        for key in ('callback','emission'):
            p[key]['utc'] = shifted(p[key]['utc'])
            p[key]['utc_ticks'] = ticks(p[key]['utc'])
    return pack(s.rows, s.pairs)


def bundle(*segments):
    return encode(dict(schema=SCHEMA, authored_sha256=AUTHORED_SHA256, segments=list(segments)))


def certify(raw):
    return certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())


def warmed(count=60, **kw):
    # End at the minute immediately before the first eligible live CLOSED bar.
    return Stream(bootstrap=certify(bundle(segment(count, shift=-count))), **kw)


@pytest.mark.parametrize('count,quarter,hour', [(1,0,0),(14,0,0),(15,1,0),(59,3,0),(60,4,1),(61,4,1)])
def test_complete_constituents_only(count, quarter, hour):
    s = Stream(bootstrap=certify(bundle(segment(count))))
    p = s.profile.snapshot()
    assert p['bootstrap_bar_count'] == count
    assert p['complete_buckets']['15m']['count'] == quarter
    assert p['complete_buckets']['1h']['count'] == hour
    assert p['market_stream'] == 'NOT_LIVE'
    assert p['processing_age']['status'] == 'UNKNOWN'
    assert p['sequence'] == 0  # Only the test's fresh HELLO, never archive sequences.
    assert p['components']['1m']['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
    assert_disabled(p)


@pytest.mark.parametrize('count,status', [(49,'INSUFFICIENT_OR_STALE_DATA'),(50,'CERTIFIED_BOOTSTRAP_ONLY')])
def test_exact_production_trend_minimum(count, status):
    p = Stream(bootstrap=certify(bundle(segment(count)))).profile.snapshot()
    assert p['components']['trend_1m']['status'] == status
    assert p['components']['trend_15m']['value'] is None
    assert p['trend_required_bars'] == {'1m':50,'15m':50,'1h':50}


def test_fifty_complete_hours_initialize_all_trends_without_live_authority():
    s = Stream(bootstrap=certify(bundle(segment(3000))))
    p = s.profile.snapshot()
    assert p['complete_buckets']['1h']['count'] == 50
    assert p['complete_buckets']['15m']['count'] == 200
    for tf in ('1m','15m','1h'):
        c = p['components']['trend_'+tf]
        assert c['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
        assert set(c['value']) == {'direction','fast_ema','slow_ema','slope'}
    assert p['analysis_status'] == 'BLOCKED'
    assert_disabled(p)


@pytest.mark.parametrize('fault', ['empty','corrupted','pin','duplicate_minute','missing_minute','out_of_order',
    'partial_line','ohlcv','bool_volume','bool_price','seal','unsealed','hash','sequence','pair_missing',
    'prior_contract','mixed_contract','rollover','authored','session','partial_callback'])
def test_untrusted_history_rejected(fault):
    item = segment(16)
    rows = [json.loads(v) for v in item['canonical_utf8'].splitlines()]
    pairs = [json.loads(v) for v in item['timing_utf8'].splitlines()]
    if fault == 'empty': raw = bundle()
    elif fault == 'corrupted': raw = b'{'
    else:
        if fault in ('duplicate_minute','missing_minute','out_of_order'):
            delta = {'duplicate_minute':-1, 'missing_minute':1, 'out_of_order':-2}[fault]
            p = pairs[1]; row = rows[p['canonical_sequence']]
            label = stamp(datetime.fromisoformat(p['source_bar_label'].replace('Z','+00:00'))+timedelta(minutes=delta))
            row['payload']['bar_time'] = p['source_bar_label'] = label
        elif fault == 'ohlcv': rows[pairs[2]['canonical_sequence']]['payload']['low'] = 999999
        elif fault == 'bool_volume': rows[pairs[2]['canonical_sequence']]['payload']['volume'] = True
        elif fault == 'bool_price': rows[pairs[2]['canonical_sequence']]['payload']['open'] = True
        elif fault in ('prior_contract','rollover'): rows[0]['payload']['contract'] = 'NQ SEP26'
        elif fault == 'mixed_contract': pairs[-1]['contract'] = 'NQ SEP26'
        elif fault == 'sequence': rows[4]['sequence'] += 1
        elif fault == 'pair_missing': pairs.pop()
        elif fault == 'session': rows[3]['session'] = str(uuid4())
        elif fault == 'partial_callback': rows.pop(-2); pairs.pop()
        item = pack(rows, pairs)
        if fault == 'partial_line': item['canonical_utf8'] = item['canonical_utf8'][:-1]
        elif fault == 'seal': item['seal_utf8'] = item['seal_utf8'].replace('"records":', '"records":1')
        elif fault == 'unsealed': item['seal_utf8'] = item['seal_utf8'].replace('true','false')
        elif fault == 'hash': item['canonical_utf8'] = item['canonical_utf8'].replace('20000','20001')
        raw = bundle(item)
        if fault == 'authored': raw = raw.replace(AUTHORED_SHA256.encode(), b'0'*64)
    with pytest.raises(ValueError):
        certify_bootstrap(raw, expected_sha256='0'*64 if fault == 'pin' else sha256(raw).hexdigest())


def test_exact_handoff_is_live_only_after_full_observed_minute():
    s = warmed()
    before = s.profile.snapshot()
    p = s.fill(3)
    assert p['live_handoff_status'] == 'COMPLETE'
    assert p['bootstrap_cutoff'] == before['bootstrap_cutoff']
    assert p['first_live_tail']['sequence'] == 1
    assert p['first_live_closed']['source_open'] == '2026-09-21T14:00:00+00:00'
    assert p['components']['1m']['data_class'] == 'LIVE_TAIL'
    assert p['components']['1h']['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
    for key in ('structure','liquidity','fvg','trend_1m'):
        assert p['components'][key]['status'] == 'SOURCE_RELATIVE_ONLY'
    assert_disabled(p)
    p = s.fill(59)
    assert p['components']['1h']['status'] == 'SOURCE_RELATIVE_ONLY'
    assert p['complete_buckets']['1h']['count'] == 2


def test_matching_overlap_never_admitted_twice_then_live_append():
    s = Stream(bootstrap=certify(bundle(segment(15))))
    p = s.fill(17)
    assert p['overlap_minutes_skipped'] == 15
    assert len(s.profile.candles) == 15
    assert p['live_handoff_status'] == 'VERIFYING_OVERLAP'
    assert p['components']['1m']['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
    p = s.fill(1)
    assert len(s.profile.candles) == 16 and p['live_handoff_status'] == 'COMPLETE'
    assert p['complete_buckets']['15m']['count'] == 1


@pytest.mark.parametrize('fault', ['gap','conflicting_overlap','heartbeat'])
def test_handoff_and_liveness_fail_closed(fault):
    if fault == 'gap': s = Stream(bootstrap=certify(bundle(segment(15, shift=-17))))
    elif fault == 'conflicting_overlap': s = Stream(bootstrap=certify(bundle(segment(15, shift=-1))))
    else: s = warmed()
    if fault == 'heartbeat':
        s.fill(3); s.qpc += 15001
    else:
        with pytest.raises(ValueError, match='BOOTSTRAP_LIVE_'):
            s.fill(3)
    p = s.profile.snapshot()
    assert p['bootstrap_status'] == p['live_handoff_status'] == 'REVOKED'
    assert all(c['value'] is None for c in p['components'].values())
    assert_disabled(p)


def test_segment_gaps_disclosed_never_complete_missing_bucket():
    data = certify(bundle(segment(8), segment(8, shift=10)))
    p = Stream(bootstrap=data).profile.snapshot()
    assert p['bootstrap_gap_count'] == 1
    assert p['complete_buckets']['15m']['count'] == 0
    assert p['complete_buckets']['1h']['count'] == 0
    with pytest.raises(ValueError, match='OVERLAP'):
        certify(bundle(segment(8), segment(8, shift=7)))


@pytest.mark.parametrize('restart', ['clean','adapter','backend','new_exporter_session'])
def test_restart_revalidates_history_without_restoring_receipts(tmp_path, monkeypatch, restart):
    raw = bundle(segment(60))
    evidence = tmp_path/'history.json'; evidence.write_bytes(raw)
    from tools.certify_analysis_bootstrap_v1 import load_bootstrap
    data = load_bootstrap(evidence, sha256(raw).hexdigest())
    if restart == 'backend':
        h = Harness(tmp_path, monkeypatch); h.runtime.bootstrap = data; h.prepare()
        adapter = h.runtime.adapter
    else:
        inbox = tmp_path/'inbox'; inbox.mkdir()
        adapter = FreshNativeAdapterV1(directory=inbox, qpc_clock=lambda: ('new-epoch',1000,1000),
                                       installed_exporter=EXPORTER, bootstrap=data)
    p = adapter.snapshot()
    assert p['adapter_status'] == 'WAITING'
    assert p['live_delivered_records'] == 0 and p['startup_cursor'] is None
    assert p['transport_liveness'] == 'UNKNOWN_OR_LOST'
    assert p['processing_age']['status'] == 'UNKNOWN'
    assert p['components']['1h']['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
    assert p['first_live_tail'] is None
    assert not p['activation_allowance_started']
    assert_disabled(p)
    adapter.close()
    evidence.write_bytes(raw+b' ')
    with pytest.raises(ValueError, match='PIN'): load_bootstrap(evidence, sha256(raw).hexdigest())


def test_new_exporter_session_cannot_reuse_old_live_sequence():
    data = certify(bundle(segment(60, shift=-60)))
    first = Stream(bootstrap=data); first.fill(3)
    # Fresh object, different exporter session, no restored live metadata.
    from backend.market_data.analysis_time_profile_v1 import MarketAnalysisTimeProfileV1, EXPORTER_SHA256
    second = MarketAnalysisTimeProfileV1(session=str(uuid4()), epoch='new', frequency=1000,
        reader_start_qpc=1000, qpc_clock=lambda: ('new',1000,1000), heartbeat_seconds=15,
        maximum_processing_seconds=90, exporter_sha256=EXPORTER_SHA256, bootstrap=data)
    p = second.snapshot()
    assert p['session'] != first.profile.session and p['sequence'] == -1
    assert p['market_stream'] == 'NOT_LIVE' and p['first_live_tail'] is None
    emitter = Stream()
    second.clock = lambda: ('new',1000,emitter.qpc)
    hello = dict(schema='arms.nt.market.v1',session=second.session,sequence=0,
                 event_time='2026-09-21T14:00:00.0000000Z',kind='HELLO',payload=HELLO)
    second.accept(encode(hello),receipt_qpc=1000)
    original = emitter.profile.accept
    def deliver(raw, paired=None, **kw):
        original(raw, paired, **kw)
        row = json.loads(raw); row['session'] = second.session; raw = encode(row)
        if paired:
            pair = json.loads(paired); pair['session'] = second.session
            pair['canonical_sha256'] = sha256(raw).hexdigest(); paired = encode(pair)
        second.accept(raw, paired, **kw)
    emitter.profile.accept = deliver
    emitter.fill(3)
    assert second.snapshot()['live_handoff_status'] == 'COMPLETE'
    assert second.snapshot()['components']['1m']['data_class'] == 'LIVE_TAIL'


def test_api_bootstrap_is_historical_only_and_no_execution_routes(forbid_account_and_execution_construction):
    s = warmed()
    with TestClient(create_market_analysis_time_app_v1(profile=s.profile)) as client:
        p = client.get('/api/v2/market-analysis/time-profile').json()
        assert p['market_stream'] == 'NOT_LIVE'
        assert p['components']['1h']['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
        assert_disabled(p)
        assert client.post('/api/v2/market-analysis/time-profile').status_code == 405
        assert client.post('/orders').status_code == 404


def test_adapter_cursor_and_live_counts_exclude_certified_archive(tmp_path, forbid_account_and_execution_construction):
    from backend.tests.test_fresh_native_adapter_sprint15y import Files
    data = certify(bundle(segment(60, shift=-60)))
    files = Files(tmp_path/'inbox')
    files.stream.qpc += 1
    a = FreshNativeAdapterV1(health_gated=False, directory=files.root, installed_exporter=EXPORTER,
        qpc_clock=lambda: (files.stream.epoch,1000,files.stream.qpc), bootstrap=data)
    files.adapter = a
    initial = a.snapshot()
    cursor = files.canonical.stat().st_size
    assert initial['live_delivered_records'] == 0 and initial['startup_cursor'] == cursor
    assert initial['bootstrap_bar_count'] == 60 and initial['bootstrap_records'] == 1
    for _ in range(3): p = files.boundary()
    assert p['adapter_status'] == 'LIVE_TAIL' and p['live_handoff_status'] == 'COMPLETE'
    assert p['live_delivered_records'] == len(files.rows)-1
    assert p['startup_cursor'] == cursor and p['bootstrap_bar_count'] == 60
    assert p['canonical_sequence'] == len(files.rows)-1
    files.stream.qpc += 15001
    p = a.snapshot()
    assert p['adapter_status'] == 'REVOKED'
    assert all(c['value'] is None for c in p['components'].values())
    assert p['live_delivered_records'] == len(files.rows)-1
    assert_disabled(p)


def test_missing_bootstrap_remains_cold_and_file_corruption_cannot_fall_back(tmp_path):
    s = Stream(); p = s.profile.snapshot()
    assert p['bootstrap_status'] == 'UNAVAILABLE' and p['bootstrap_bar_count'] == 0
    assert not s.profile.candles
    from tools.certify_analysis_bootstrap_v1 import load_bootstrap
    with pytest.raises(FileNotFoundError): load_bootstrap(tmp_path/'missing.json','0'*64)


@pytest.mark.parametrize('backend_shutdown', [False, True])
def test_actual_adapter_restart_with_running_exporter_does_not_replay_cursor(tmp_path, backend_shutdown):
    from backend.tests.test_fresh_native_adapter_sprint15y import Files
    data = certify(bundle(segment(60)))
    files = Files(tmp_path/'inbox')
    def fresh():
        files.stream.qpc += 1
        return FreshNativeAdapterV1(health_gated=False, directory=files.root, installed_exporter=EXPORTER,
            qpc_clock=lambda: (files.stream.epoch,1000,files.stream.qpc), bootstrap=data)
    prior = fresh(); files.adapter = prior; prior.poll()
    for _ in range(4): files.boundary()
    assert prior.status == 'LIVE_TAIL'
    if backend_shutdown:
        with TestClient(create_market_analysis_time_app_v1(adapter=prior)) as client:
            assert client.get('/api/v2/market-analysis/time-profile').status_code == 200
        assert prior.status == 'DISCONNECTED'  # Application lifespan really closed the old adapter.
    else: prior.close()
    restarted = fresh(); files.adapter = restarted
    p = restarted.snapshot()
    assert p['adapter_status'] == 'BOOTSTRAP' and p['live_delivered_records'] == 0
    assert p['first_live_tail'] is None and p['market_stream'] == 'NOT_LIVE'
    assert p['startup_cursor'] == files.canonical.stat().st_size
    discarded = p['bootstrap_records']
    for _ in range(3): p = files.boundary()
    assert p['adapter_status'] == 'LIVE_TAIL', p['adapter_reason']
    assert p['live_handoff_status'] == 'VERIFYING_OVERLAP'
    assert p['overlap_minutes_skipped'] == 1
    assert p['bootstrap_records'] >= discarded
    assert p['live_delivered_records'] == len(files.rows)-p['bootstrap_records']
    assert len(restarted.profile.candles) == 60
    restarted.close()


def test_real_archived_native_evidence_is_insufficient_for_hour_warmup():
    capture = json.loads(Path('backend/tests/production_timing_sprint15w.json').read_text())['native_capture']
    item = {key: capture['native_'+name+'_utf8'] for key,name in
            [('canonical_utf8','canonical'),('timing_utf8','timing'),('seal_utf8','seal')]}
    data = certify(bundle(item))
    assert 0 < len(data.bars) < 15
    p = Stream(bootstrap=data).profile.snapshot()
    assert p['complete_buckets']['1h']['count'] == 0
    assert p['components']['trend_1m']['value'] is None
    assert p['market_stream'] == 'NOT_LIVE'
