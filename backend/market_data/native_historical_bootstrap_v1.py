"""Offline native repository history; no current-time, feed or execution authority.

The out-of-band bundle pin binds evidence, not provider authenticity. Calendar
intervals must agree with the reviewed XML AND the captured native iterator.
"""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import xml.etree.ElementTree as ET
from uuid import UUID

from backend.market_data.certified_bootstrap_v1 import (
    CertifiedBootstrap, MAX_BARS, _bar, _lines, require,
)
from backend.market_data.loaded_calendar_binding_v1 import CHICAGO, DAYS, _session, _wall
from tools.production_timing_v1 import parse
from tools.native_timing_witness_v1 import ticks, MINUTE as MINUTE_TICKS

SCHEMA = 'arms.certified-native-history.v1'
EXPORTER_SHA256 = '836ad9d128853129119bd9ea97b93158f6bfaa2f6bf216d80679a53c6e1ef578'
TEMPLATE_SHA256 = '370b17f23eeea694e686394b5fdb9b55681089c22d5232d5e6a354a314325620'
TEMPLATE = 'CME US Index Futures ETH'
MINUTE = timedelta(minutes=1)
IDENTITY = dict(instrument='NQ', contract='NQ DEC26', bars_type='Minute', bars_value=1,
                template=TEMPLATE, classification='HISTORICAL', realtime=False)
HEADER = dict(schema='arms.nt.historical-bootstrap.header.v1', exporter='ArmsHistoricalBootstrapV1/1',
    sdk_version='8.1.8.2', source='NINJATRADER_LOCAL_REPOSITORY', provider_attribution='UNATTESTED',
    expiry='2026-12-01', market_data_type='Last', template_timezone='Central Standard Time',
    application_timezone='UTC', bar_label='CLOSE', tick_size=.25, point_value=20,
    lookup_policy='Repository', merge_policy='DoNotMerge', reset_on_new_trading_day=True,
    split_adjusted=False, dividend_adjusted=False, excluded_first_and_last=True,
    observation_only=True, runtime_admission=False, **IDENTITY)


def instant(value):
    require(type(value) is str and value.endswith('Z'), 'HISTORY_NATIVE_UTC_REQUIRED')
    result = datetime.fromisoformat(value)
    require(ticks(value) % MINUTE_TICKS == 0, 'HISTORY_MINUTE_LABEL')
    return result


def exact(value, expected):
    return all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items())


def calendar_intervals(template, begin, end):
    """Only pinned ETH definitions; unsupported exceptions remain UNKNOWN, never guessed."""
    require(type(template) is bytes and sha256(template).hexdigest() == TEMPLATE_SHA256,
            'UNKNOWN_GAP_TEMPLATE_IDENTITY')
    require(begin.tzinfo == timezone.utc and end.tzinfo == timezone.utc
            and begin.year == end.year == 2026
            and timedelta(0) < end-begin <= timedelta(days=24), 'UNKNOWN_GAP_CALENDAR_RANGE')
    t = ET.fromstring(template).find('TradingHours')
    require(t.findtext('Name') == TEMPLATE and t.findtext('TimeZone') == 'Central Standard Time',
            'UNKNOWN_GAP_CALENDAR_METADATA')
    sessions = [_session(n) for n in t.find('Sessions')]
    holidays = {n.findtext('Date')[:10] for n in t.find('HolidaysSerializable')}
    partial = {n.findtext('Date')[:10]: n for n in t.find('PartialHolidaysSerializable')}
    day = begin.astimezone(CHICAGO).date()-timedelta(days=2)
    last = end.astimezone(CHICAGO).date()+timedelta(days=2)
    intervals = []
    while day <= last:
        if day.isoformat() not in holidays:
            for s in sessions:
                if s['trading_day'] != DAYS[day.weekday()]:
                    continue
                start_day = day-timedelta(days=(day.weekday()-DAYS.index(s['begin_day'])) % 7)
                require(s['end_day'] == DAYS[day.weekday()], 'UNKNOWN_GAP_SESSION_SHAPE')
                start, stop = _wall(start_day, s['begin_time']), _wall(day, s['end_time'])
                override = partial.get(day.isoformat())
                if override is not None:
                    c = _session(override.find('Constraint'))
                    require(override.findtext('IsEarlyEnd') == 'true'
                            and override.findtext('IsLateBegin') == 'false'
                            and len(override.find('Sessions')) == 0
                            and c['end_day'] == DAYS[day.weekday()], 'UNKNOWN_GAP_UNSUPPORTED_EXCEPTION')
                    stop = _wall(day, c['end_time'])
                if start < stop and stop >= begin and start < end:
                    intervals.append((start, stop, day.isoformat()))
        day += timedelta(days=1)
    intervals.sort()
    require(intervals and all(a[1] < b[0] for a, b in zip(intervals, intervals[1:])),
            'UNKNOWN_GAP_CALENDAR_OVERLAP')
    return int(t.findtext('Version')), tuple(intervals)


def classify_gap(previous, following, intervals=(), coverage=()):
    """CLOSE labels: every missing minute must be outside verified open sessions."""
    if following <= previous:
        return 'INVALID_ORDER'
    if following == previous+MINUTE:
        return 'CONTIGUOUS'
    if not coverage or not coverage[0] <= previous < following <= coverage[1]:
        return 'UNKNOWN_GAP'
    if not any(start <= following-MINUTE and following <= stop for start, stop, _ in intervals):
        return 'UNKNOWN_GAP'  # A purported first live candle during closure is not a proven join.
    # Partial minutes intersecting an open session are not excused as closed time.
    if any(previous < stop and following-MINUTE > start for start, stop, _ in intervals):
        return 'UNEXPECTED_DATA_GAP'
    return 'EXPECTED_SESSION_GAP'


def certify_native_history(bundle, digest):
    require(set(bundle) == {'schema','authored_sha256','history_utf8','seal_utf8','template_utf8'}
            and bundle['schema'] == SCHEMA and bundle['authored_sha256'] == EXPORTER_SHA256,
            'HISTORY_EXPORTER_IDENTITY')
    raw, lines = _lines(bundle['history_utf8'])
    require(2 <= len(lines) <= MAX_BARS+1, 'HISTORY_BAR_COUNT')
    h = parse(lines[0])
    require(set(h) == set(HEADER) | {'dataset','template_version','requested_from','requested_through',
            'calendar_from','calendar_through','calendar_intervals','returned_bar_count'} and exact(h, HEADER),
            'HISTORY_IDENTITY')
    dataset = h['dataset']
    require(str(UUID(dataset)) == dataset, 'HISTORY_DATASET_UUID')
    first, last = date.fromisoformat(h['requested_from']), date.fromisoformat(h['requested_through'])
    require(first.year == last.year == 2026 and 0 <= (last-first).days <= 14, 'HISTORY_REQUEST_RANGE')
    coverage = (instant(h['calendar_from']), instant(h['calendar_through']))
    require(coverage[0].date() == first-timedelta(days=2)
            and coverage[1].date() == last+timedelta(days=8)
            and coverage[0].hour == coverage[1].hour == coverage[0].minute == coverage[1].minute == 0,
            'HISTORY_CALENDAR_COVERAGE')
    version, intervals = calendar_intervals(bundle['template_utf8'].encode('utf-8'), *coverage)
    require(type(h['template_version']) is int and h['template_version'] == version,
            'HISTORY_TEMPLATE_VERSION')
    actual = h['calendar_intervals']
    require(type(actual) is list and 0 < len(actual) <= 64
            and all(set(v) == {'begin','end','trading_day'} for v in actual), 'UNKNOWN_GAP_ITERATOR_SCHEMA')
    actual = tuple((instant(v['begin']), instant(v['end']), v['trading_day']) for v in actual)
    require(actual == intervals, 'UNKNOWN_GAP_ITERATOR_MISMATCH')
    require(type(bundle['seal_utf8']) is str and len(bundle['seal_utf8']) <= 4096, 'HISTORY_SEAL_SIZE')
    seal = parse(bundle['seal_utf8'].encode('utf-8'))
    expected_seal = dict(schema='arms.nt.historical-bootstrap.seal.v1', dataset=dataset, bytes=len(raw),
        records=len(lines), bars=len(lines)-1, sha256=sha256(raw).hexdigest(), writer_closed=True,
        complete=True, classification='HISTORICAL', runtime_admission=False)
    require(set(seal) == set(expected_seal) and exact(seal, expected_seal), 'HISTORY_SEAL_INTEGRITY')
    require(type(h['returned_bar_count']) is int and h['returned_bar_count'] == len(lines)+1,
            'HISTORY_BOUNDARY_EXCLUSION')
    bars, gaps = [], []
    for index, line in enumerate(lines[1:]):
        row = parse(line)
        expected = dict(schema='arms.nt.historical-bootstrap.bar.v1', dataset=dataset, index=index,
                        source_index=index+1, bar_time_kind='Utc', **IDENTITY)
        require(set(row) == set(expected) | {'bar_time','open','high','low','close','volume'}
                and exact(row, expected), 'HISTORY_BAR_IDENTITY_OR_INDEX')
        bar = _bar({k: row[k] for k in ('bar_time','open','high','low','close','volume')})
        label = instant(bar.label)
        require(coverage[0] <= label <= coverage[1]
                and any(start <= label-MINUTE and label <= stop for start, stop, _ in intervals),
                'HISTORY_BAR_OUTSIDE_SESSION')
        # Date-based requests can encompass the overnight portion of a trading day.
        require(first-timedelta(days=1) <= label.date() <= last+timedelta(days=1), 'HISTORY_OUTSIDE_REQUEST')
        if bars:
            prior = instant(bars[-1].label)
            status = classify_gap(prior, label, intervals, coverage)
            require(status in ('CONTIGUOUS','EXPECTED_SESSION_GAP'), status)
            if status != 'CONTIGUOUS':
                gaps.append((bars[-1].label, bar.label, status, int((label-prior)/MINUTE)-1))
        bars.append(bar)
    return CertifiedBootstrap(digest, tuple(bars), (dataset,), len(gaps),
        source='NATIVE_HISTORICAL_REPOSITORY', calendar_intervals=intervals,
        calendar_coverage=coverage, gap_report=tuple(gaps))


def report(data):
    """Recompute warm-up counts with the production aggregator, not count/period guesses."""
    from backend.backtesting.closed_bar_aggregator_v1 import ClosedBarAggregatorV1
    aggregator = ClosedBarAggregatorV1(history_limit=50)
    for bar in data.bars:
        aggregator.update_completed(bar.candle())
    counts = dict(aggregator.emitted_counts)
    return dict(certification_version=SCHEMA, certification_sha256=data.sha256,
        classification='CERTIFIED_BOOTSTRAP', source=data.source, provider_attribution='UNATTESTED',
        contract='NQ DEC26', timeframe='1m', template=TEMPLATE, template_sha256=TEMPLATE_SHA256,
        bars=len(data.bars), first_label=data.bars[0].label, last_label=data.bars[-1].label,
        duplicate_count=0, ohlcv_status='VALID', gap_report=data.gap_report,
        completed_buckets=counts, trend_ready=dict(**{'1m':len(data.bars)>=50},
            **{tf:counts[tf]>=50 for tf in ('15m','1h')}),
        live_records=0, absolute_recency='UNKNOWN', session_authority='UNKNOWN', news_authority='UNCERTIFIED')
