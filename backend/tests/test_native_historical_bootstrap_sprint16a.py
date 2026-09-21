"""Synthetic native-shaped history proves logic, NOT a real native capture.

The XML fixture is the reviewed static template, not market data. The account
and execution-construction traps remain active throughout these tests.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

import pytest

from backend.market_data.certified_bootstrap_v1 import certify_bootstrap
from backend.market_data.native_historical_bootstrap_v1 import (
    HEADER, IDENTITY, SCHEMA, EXPORTER_SHA256, TEMPLATE_SHA256, calendar_intervals,
    classify_gap, report,
)
from backend.tests.test_analysis_time_sprint15x import (
    Stream, encode, stamp, assert_disabled, forbid_account_and_execution_construction,
)
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1
from tools.certify_native_history_v1 import build_bundle

UTC = timezone.utc
MINUTE = timedelta(minutes=1)
TEMPLATE = json.loads(Path('backend/tests/fixtures/historical_template_sprint16a.json').read_text())['template_utf8'].encode()
SOURCE = Path('integrations/ninjatrader/ArmsHistoricalBootstrapV1.cs').read_bytes()


def native_shape(count=60, start='2026-09-21T13:01:00Z', through='2026-09-21'):
    """Construct SYNTHETIC fixture; advance only over verified open session minutes."""
    beginning = datetime.fromisoformat(start)
    first = beginning.date()
    last = datetime.fromisoformat(through).date()
    coverage = (datetime.combine(first-timedelta(days=2), datetime.min.time(), UTC),
                datetime.combine(last+timedelta(days=8), datetime.min.time(), UTC))
    version, intervals = calendar_intervals(TEMPLATE, *coverage)
    dataset = str(uuid4())
    header = dict(HEADER, dataset=dataset, template_version=version,
        requested_from=first.isoformat(), requested_through=through,
        calendar_from=stamp(coverage[0]), calendar_through=stamp(coverage[1]),
        calendar_intervals=[dict(begin=stamp(a), end=stamp(b), trading_day=d) for a,b,d in intervals],
        returned_bar_count=count+2)
    rows = []
    label = beginning
    for i in range(count):
        while not any(a <= label-MINUTE and label <= b for a,b,_ in intervals):
            label += MINUTE
            assert label <= coverage[1], 'fixture coverage exhausted'
        rows.append(dict(schema='arms.nt.historical-bootstrap.bar.v1', dataset=dataset,
            index=i, source_index=i+1, bar_time_kind='Utc', **IDENTITY, bar_time=stamp(label),
            open=20000, high=20001, low=19999, close=20000.25, volume=0))
        label += MINUTE
    return header, rows


def pack(header, rows):
    raw = b'\n'.join(encode(r) for r in [header]+rows)+b'\n'
    seal = encode(dict(schema='arms.nt.historical-bootstrap.seal.v1', dataset=header['dataset'],
        bytes=len(raw), records=len(rows)+1, bars=len(rows), sha256=sha256(raw).hexdigest(),
        writer_closed=True, complete=True, classification='HISTORICAL', runtime_admission=False))
    return raw, seal


def bundle(header, rows):
    raw, seal = pack(header, rows)
    return encode(dict(schema=SCHEMA, authored_sha256=EXPORTER_SHA256, history_utf8=raw.decode(),
                       seal_utf8=seal.decode(), template_utf8=TEMPLATE.decode()))


def certified(header, rows):
    raw = bundle(header, rows)
    return certify_bootstrap(raw, expected_sha256=sha256(raw).hexdigest())


@pytest.mark.parametrize('count,quarters,hours,trend', [(1,0,0,False),(14,0,0,False),
    (15,1,0,False),(49,3,0,False),(50,3,0,True),(59,3,0,True),(60,4,1,True)])
def test_exact_minimums_and_zero_volume(count, quarters, hours, trend):
    data = certified(*native_shape(count))
    p = Stream(bootstrap=data).profile.snapshot()
    assert report(data)['completed_buckets'] == {'15m':quarters,'1h':hours}
    assert report(data)['trend_ready']['1m'] == trend
    assert p['bootstrap_source'] == 'NATIVE_HISTORICAL_REPOSITORY'
    assert p['bootstrap_provider_attribution'] == 'UNATTESTED'
    assert p['market_stream'] == 'NOT_LIVE' and p['sequence'] == 0
    assert p['processing_age']['status'] == 'UNKNOWN'
    assert_disabled(p)


def test_sufficient_synthetic_history_all_trends_restart_without_receipts(tmp_path):
    h, rows = native_shape(3600, '2026-09-14T00:01:00Z', '2026-09-18')
    data = certified(h, rows)
    assert data.gap_count == 2
    r = report(data)
    assert r['completed_buckets'] == {'15m':240, '1h':60}
    assert r['trend_ready'] == {'1m':True,'15m':True,'1h':True}
    for _ in range(2):
        # Independent reconstruction from pinned raw evidence, no restored clock/cursor.
        data = certified(h, rows)
        inbox = tmp_path/str(uuid4()); inbox.mkdir()
        a = FreshNativeAdapterV1(directory=inbox, qpc_clock=lambda: ('fresh',1000,1000),
            installed_exporter=Path('integrations/ninjatrader/ArmsReadOnlyMarketV1.cs').resolve(), bootstrap=data)
        p = a.snapshot()
        assert p['live_delivered_records'] == 0 and p['startup_cursor'] is None
        assert p['transport_liveness'] == 'UNKNOWN_OR_LOST'
        for tf in ('1m','15m','1h'):
            assert p['components']['trend_'+tf]['status'] == 'CERTIFIED_BOOTSTRAP_ONLY'
        assert_disabled(p)
        a.close()


@pytest.mark.parametrize('fault', ['duplicate','order','gap','ohlc','tick','volume','bool_volume',
    'contract','mixed','template','adjusted','provider_lookup','realtime','index','source_index',
    'kind','utc','unclosed','sdk','uuid','calendar','seal','pin','source','template_bytes','extra','range'])
def test_fail_closed_mutations(fault):
    h, rows = native_shape()
    if fault == 'duplicate': rows[1]['bar_time'] = rows[0]['bar_time']
    elif fault == 'order': rows[1]['bar_time'] = stamp(datetime.fromisoformat(rows[0]['bar_time'])-MINUTE)
    elif fault == 'gap': rows[1]['bar_time'] = rows[2]['bar_time']
    elif fault == 'ohlc': rows[1]['low'] = 30000
    elif fault == 'tick': rows[1]['close'] = 20000.1
    elif fault == 'volume': rows[1]['volume'] = -1
    elif fault == 'bool_volume': rows[1]['volume'] = False
    elif fault == 'contract': h['contract'] = 'NQ SEP26'
    elif fault == 'mixed': rows[1]['contract'] = 'NQ SEP26'
    elif fault == 'template': h['template'] = 'Default'
    elif fault == 'adjusted': h['merge_policy'] = 'MergeBackAdjusted'
    elif fault == 'provider_lookup': h['lookup_policy'] = 'Provider'
    elif fault == 'realtime': rows[1]['realtime'] = True
    elif fault == 'index': rows[1]['index'] = 4
    elif fault == 'source_index': rows[1]['source_index'] = 0
    elif fault == 'kind': rows[1]['bar_time_kind'] = 'Unspecified'
    elif fault == 'utc': rows[1]['bar_time'] = rows[1]['bar_time'].replace('Z','+00:00')
    elif fault == 'unclosed': h['excluded_first_and_last'] = False
    elif fault == 'sdk': h['sdk_version'] = 'UNKNOWN'
    elif fault == 'uuid': h['dataset'] = 'invalid'
    elif fault == 'calendar': h['calendar_intervals'].pop()
    elif fault == 'extra': rows[0]['account'] = 'forbidden'
    elif fault == 'range': h['requested_from'] = '2025-01-01'
    value = json.loads(bundle(h, rows))
    if fault == 'seal': value['seal_utf8'] = value['seal_utf8'].replace('true','false')
    elif fault == 'source': value['authored_sha256'] = '0'*64
    elif fault == 'template_bytes': value['template_utf8'] += ' '
    raw = encode(value)
    with pytest.raises(ValueError):
        certify_bootstrap(raw, expected_sha256='0'*64 if fault == 'pin' else sha256(raw).hexdigest())


@pytest.mark.parametrize('before,after,status', [
    ('2026-09-21T21:00:00Z','2026-09-21T22:01:00Z','EXPECTED_SESSION_GAP'),
    ('2026-09-25T21:00:00Z','2026-09-27T22:01:00Z','EXPECTED_SESSION_GAP'),
    ('2026-09-21T20:59:00Z','2026-09-21T22:01:00Z','UNEXPECTED_DATA_GAP'),
    ('2026-09-21T13:00:00Z','2026-09-21T13:02:00Z','UNEXPECTED_DATA_GAP'),
    ('2026-09-25T21:00:00Z','2026-09-25T22:00:00Z','UNKNOWN_GAP'),
    ('2026-08-21T21:00:00Z','2026-09-21T22:01:00Z','UNKNOWN_GAP')])
def test_gap_classifications(before, after, status):
    data = certified(*native_shape())
    assert classify_gap(datetime.fromisoformat(before),datetime.fromisoformat(after),
        data.calendar_intervals, data.calendar_coverage) == status
    assert classify_gap(datetime.fromisoformat(before),datetime.fromisoformat(after)) == 'UNKNOWN_GAP'


def test_daily_gap_dataset_and_partial_htf_not_filled():
    data = certified(*native_shape(20, '2026-09-21T20:51:00Z', '2026-09-22'))
    assert data.gap_count == 1 and data.gap_report[0][2:] == ('EXPECTED_SESSION_GAP',60)
    assert report(data)['completed_buckets'] == {'15m':0,'1h':0}


@pytest.mark.parametrize('day,start,stop', [
    ('2026-11-26','2026-11-25T23:00:00Z','2026-11-26T18:00:00Z'),
    ('2026-11-27','2026-11-26T23:00:00Z','2026-11-27T18:15:00Z'),
    ('2026-11-02','2026-11-01T23:00:00Z','2026-11-02T22:00:00Z')])
def test_static_early_close_and_dst_scope(day, start, stop):
    begin = datetime.fromisoformat(day).replace(tzinfo=UTC)
    _, intervals = calendar_intervals(TEMPLATE, begin-timedelta(days=2), begin+timedelta(days=3))
    assert (datetime.fromisoformat(start),datetime.fromisoformat(stop),day) in intervals


def test_full_holiday_closure_and_unknown_calendar_fail_closed():
    begin = datetime(2026,12,23,tzinfo=UTC); end = datetime(2026,12,29,tzinfo=UTC)
    _, intervals = calendar_intervals(TEMPLATE, begin, end)
    assert not any(day == '2026-12-25' for _,_,day in intervals)
    assert classify_gap(datetime(2026,12,24,18,15,tzinfo=UTC),datetime(2026,12,27,23,1,tzinfo=UTC),
                        intervals,(begin,end)) == 'EXPECTED_SESSION_GAP'
    with pytest.raises(ValueError, match='UNKNOWN_GAP'):
        calendar_intervals(TEMPLATE+b' ',begin,end)
    with pytest.raises(ValueError, match='UNKNOWN_GAP'):
        calendar_intervals(TEMPLATE,begin,datetime(2027,1,2,tzinfo=UTC))


def test_expected_gap_handoff_requires_new_live_cursor_and_full_observed_bar(monkeypatch):
    data = certified(*native_shape(60, '2026-09-25T20:01:00Z', '2026-09-25'))
    # Synthetic fresh live stream starts Sunday at 22:00; its first eligible
    # CLOSED minute is 22:01 after the first forming bar was quarantined.
    monkeypatch.setattr('backend.tests.test_analysis_time_sprint15x.BASE', datetime(2026,9,27,22,tzinfo=UTC))
    s = Stream(bootstrap=data)
    p = s.fill(3)
    assert p['live_handoff_status'] == 'COMPLETE'
    assert p['handoff_gap']['classification'] == 'EXPECTED_SESSION_GAP'
    assert p['first_live_tail']['sequence'] == 1
    assert p['first_live_closed']['source_open'] == '2026-09-27T22:00:00+00:00'
    assert p['components']['1m']['data_class'] == 'LIVE_TAIL'
    assert p['components']['1h']['data_class'] == 'CERTIFIED_BOOTSTRAP'
    assert_disabled(p)


def test_missing_open_minute_cannot_be_excused_at_handoff():
    data = certified(*native_shape(59))  # Ends 13:59; first live CLOSED 14:01 => missing 14:00.
    s = Stream(bootstrap=data)
    with pytest.raises(ValueError, match='BOOTSTRAP_LIVE_GAP'): s.fill(3)
    assert s.profile.snapshot()['bootstrap_status'] == 'REVOKED'


def test_overlap_checked_never_readded_then_contiguous_live_append():
    h, rows = native_shape(2, '2026-09-21T14:01:00Z')
    for i,r in enumerate(rows,1):
        r.update(open=20000+i*.25,high=20001+i*.25,low=19999+i*.25,close=20000.25+i*.25,volume=10)
    s = Stream(bootstrap=certified(h, rows)); p = s.fill(4)
    assert p['overlap_minutes_skipped'] == 2 and len(s.profile.candles) == 2
    p = s.fill(1)
    assert p['live_handoff_status'] == 'COMPLETE' and len(s.profile.candles) == 3
    rows[0]['volume'] = 0
    s = Stream(bootstrap=certified(h, rows))
    with pytest.raises(ValueError, match='OVERLAP_CONFLICT'): s.fill(3)


def test_cli_bundle_validation_and_source_pin():
    h, rows = native_shape()
    raw, seal = pack(h, rows)
    bundle_raw, r = build_bundle(raw, seal, TEMPLATE, SOURCE)
    assert r['classification'] == 'CERTIFIED_BOOTSTRAP' and r['live_records'] == 0
    assert r['certification_sha256'] == sha256(bundle_raw).hexdigest()
    assert r['provider_attribution'] == 'UNATTESTED'
    with pytest.raises(ValueError, match='SOURCE_CHANGED'): build_bundle(raw, seal, TEMPLATE, SOURCE+b' ')
    assert sha256(TEMPLATE).hexdigest() == TEMPLATE_SHA256


def test_exporter_separate_opt_in_repository_only_no_execution():
    text = SOURCE.decode()
    assert sha256(SOURCE.replace(b'\r\n',b'\n')).hexdigest() == EXPORTER_SHA256
    for required in ('CaptureEnabled = false','LookupPolicies.Repository','MergePolicy.DoNotMerge',
                     'request.Request(Completed)','i = 1; i < returned - 1','FileMode.CreateNew'):
        assert required in text
    for forbidden in ('Account.', 'Account[', 'CreateOrder(', '.Submit(', '.Change(', '.Cancel(',
                      '.Update +=', 'LookupPolicies.Provider', 'Connection.Connect(', 'AddDataSeries('):
        assert forbidden not in text
