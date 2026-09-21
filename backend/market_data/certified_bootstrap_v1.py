"""Offline, hash-pinned native history. Never a receipt, heartbeat or live cursor.

The pin is supplied out of band after review. Hashes bind bytes, not writer
authenticity; acquisition remains inside the operator-controlled native boundary.
No CSV, adjusted/continuous futures, persisted authority or clock restoration.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from math import isfinite
from uuid import UUID

from backend.models.candle import Candle
from tools.native_timing_witness_v1 import IDENTITY, MINUTE, check_pair, ticks
from tools.production_timing_v1 import PAIR_FIELDS, SEAL_FIELDS, parse

SCHEMA = 'arms.certified-bootstrap.v1'
MAX_BYTES = 64 * 1024 * 1024
MAX_BARS = 10000
DATA_CLASSES = ('CERTIFIED_BOOTSTRAP', 'LIVE_TAIL', 'UNTRUSTED_HISTORY', 'REVOKED')
HELLO = dict(provider='Provider31', contract='NQ DEC26', expiry='2026-12-01', instrument='NQ',
             tick_size=.25, point_value=20, timeframe='1m', trading_hours_template='CME US Index Futures ETH',
             source_timezone='UTC', bar_label='CLOSE', realtime=True, read_only=True)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


@dataclass(frozen=True)
class BootstrapBar:
    label: str  # Original canonical CLOSE label, converted only when constructing a Candle.
    open: float
    high: float
    low: float
    close: float
    volume: int

    def candle(self):
        return Candle('NQ', '1m', self.open, self.high, self.low, self.close, self.volume,
                      datetime.fromisoformat(self.label.replace('Z', '+00:00'))-timedelta(minutes=1))


@dataclass(frozen=True)
class CertifiedBootstrap:
    sha256: str
    bars: tuple
    sessions: tuple
    gap_count: int
    source: str = 'SEALED_NATIVE_PRODUCTION'
    calendar_intervals: tuple = ()
    calendar_coverage: tuple = ()
    gap_report: tuple = ()


def _lines(raw):
    require(type(raw) is str, 'BOOTSTRAP_RAW_TYPE')
    encoded = raw.encode('utf-8')
    require(0 < len(encoded) <= MAX_BYTES and encoded.endswith(b'\n'), 'BOOTSTRAP_TRUNCATED')
    result = encoded.split(b'\n')[:-1]
    result = [v[:-1] if v.endswith(b'\r') else v for v in result]
    require(len(result) <= 200000 and all(0 < len(v) <= 16384 and b'\r' not in v for v in result),
            'BOOTSTRAP_LINE_LIMIT')
    return encoded, result


def _bar(payload):
    require(set(payload) == set('bar_time open high low close volume'.split()), 'BOOTSTRAP_CANDLE_SCHEMA')
    require(all(type(payload[k]) in (int, float) and isfinite(payload[k]) and payload[k] > 0
                and payload[k]*4 == int(payload[k]*4) for k in ('open', 'high', 'low', 'close'))
            and type(payload['volume']) is int and 0 <= payload['volume'] < 2**63
            and payload['low'] <= min(payload['open'], payload['close'])
            <= max(payload['open'], payload['close']) <= payload['high'], 'BOOTSTRAP_OHLCV')
    require(ticks(payload['bar_time']) % MINUTE == 0, 'BOOTSTRAP_MINUTE_LABEL')
    return BootstrapBar(payload['bar_time'], *[payload[k] for k in ('open','high','low','close','volume')])


def _segment(segment):
    require(set(segment) == {'canonical_utf8', 'timing_utf8', 'seal_utf8'}, 'BOOTSTRAP_SEGMENT_SCHEMA')
    canonical, rows = _lines(segment['canonical_utf8'])
    timing, pairs = _lines(segment['timing_utf8'])
    require(type(segment['seal_utf8']) is str and len(segment['seal_utf8']) <= 4096, 'BOOTSTRAP_SEAL_SIZE')
    seal = parse(segment['seal_utf8'].encode())
    require(set(seal) == SEAL_FIELDS and seal['schema'] == 'arms.nt.production-timing.seal.v1', 'BOOTSTRAP_SEAL')
    session = seal['session']
    require(str(UUID(session)) == session and all(seal[k] is True for k in
            ('canonical_writer_closed', 'timing_writer_closed', 'complete')), 'BOOTSTRAP_WRITER_NOT_CLOSED')
    require(all(type(seal[k]) is int for k in ('records', 'bytes', 'canonical_records'))
            and seal['records'] == len(pairs) and seal['bytes'] == len(timing)
            and seal['canonical_records'] == len(rows) and seal['sha256'] == sha256(timing).hexdigest(),
            'BOOTSTRAP_SEAL_INTEGRITY')
    result = []
    previous = forming = pending = None
    formed = pair_index = 0
    frequency = None
    for sequence, raw in enumerate(rows):
        row = parse(raw)
        require(set(row) == set('schema session sequence event_time kind payload'.split())
                and row['schema'] == 'arms.nt.market.v1' and row['session'] == session
                and type(row['sequence']) is int and row['sequence'] == sequence, 'BOOTSTRAP_SEQUENCE')
        ticks(row['event_time'])
        kind, value = row['kind'], row['payload']
        if sequence == 0:
            require(kind == 'HELLO' and value == HELLO and value['realtime'] is True
                    and value['read_only'] is True, 'BOOTSTRAP_CONTRACT_OR_IDENTITY')
            continue
        if sequence == len(rows)-1:
            require(kind == 'DISCONNECTED' and value.get('connected') is False and pending is None,
                    'BOOTSTRAP_TERMINAL')
            continue
        if kind == 'HEARTBEAT':
            require(value == {'connected': True} and value['connected'] is True and pending is None,
                    'BOOTSTRAP_HEARTBEAT_SCHEMA')
            continue
        require(kind in ('CLOSED', 'FORMING') and pair_index < len(pairs), 'BOOTSTRAP_PAIR_REQUIRED')
        bar = _bar(value)
        p = parse(pairs[pair_index])
        require(set(p) == PAIR_FIELDS and p['schema'] == 'arms.nt.production-timing.v1', 'BOOTSTRAP_PAIR_SCHEMA')
        require(all(type(p[k]) is int for k in ('pair_sequence','canonical_sequence','qpc_frequency',
                'callback_index','bar_index','bars_ago','bars_in_progress','bars_value')), 'BOOTSTRAP_PAIR_INTEGER')
        require(p['session'] == session and p['canonical_sequence'] == sequence and p['pair_sequence'] == pair_index
                and p['kind'] == kind and p['canonical_sha256'] == sha256(raw).hexdigest()
                and p['source_bar_label'] == bar.label, 'BOOTSTRAP_PAIR_BINDING')
        require(all(p[k] == v for k,v in IDENTITY.items()) and p['state'] == 'Realtime'
                and p['bars_in_progress'] == 0 and p['first_tick'] is True
                and p['observation_only'] is True and p['runtime_admission'] is False, 'BOOTSTRAP_PROVENANCE')
        cb, em = p['callback'], p['emission']
        check_pair(cb); check_pair(em)
        require(p['qpc_frequency'] > 0 and (frequency is None or frequency == p['qpc_frequency'])
                and cb['qpc_after'] <= em['qpc_before'] and cb['utc_ticks'] <= em['utc_ticks']
                and em['utc'] == row['event_time'], 'BOOTSTRAP_PAIR_ORDER')
        if previous:
            require(previous['emission']['qpc_after'] <= em['qpc_before']
                    and previous['emission']['utc_ticks'] <= em['utc_ticks'], 'BOOTSTRAP_EMISSION_REGRESSION')
            if previous['callback'] != cb:
                require(previous['emission']['qpc_after'] <= cb['qpc_before']
                        and previous['emission']['utc_ticks'] <= cb['utc_ticks'], 'BOOTSTRAP_CALLBACK_REGRESSION')
        frequency = p['qpc_frequency']
        require(p['bar_index'] >= 0 and p['bar_index'] == p['callback_index']-p['bars_ago'], 'BOOTSTRAP_BAR_INDEX')
        if kind == 'CLOSED':
            require(formed >= 2 and pending is None and p['bars_ago'] == 1
                    and forming['bar_index'] == p['bar_index'] and forming['source_bar_label'] == bar.label,
                    'BOOTSTRAP_CLOSED_PROVENANCE')
            require(cb['utc_ticks'] >= ticks(bar.label), 'BOOTSTRAP_CLOSED_BEFORE_LABEL')
            pending = (p, bar)
        else:
            require(p['bars_ago'] == 0 and ((formed >= 2) == (pending is not None)), 'BOOTSTRAP_MISSING_CLOSED')
            if forming:
                require(p['bar_index'] == forming['bar_index']+1
                        and ticks(bar.label) == ticks(forming['source_bar_label'])+MINUTE, 'BOOTSTRAP_MINUTE_ORDER_OR_GAP')
            if pending:
                require(pending[0]['callback'] == cb and pending[0]['callback_index'] == p['callback_index'],
                        'BOOTSTRAP_SAME_CALLBACK')
                result.append(pending[1])
            pending = None
            forming = p
            formed += 1
        previous = p
        pair_index += 1
    require(pair_index == len(pairs) and pending is None and result, 'BOOTSTRAP_EMPTY_OR_EXTRA_PAIRS')
    return session, result


def certify_bootstrap(raw, *, expected_sha256):
    """Revalidate raw evidence on every restart. An absent pin is not trust."""
    from backend.market_data.exporter_identity_v1 import AUTHORED_SHA256
    try:
        require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'BOOTSTRAP_SIZE')
        require(type(expected_sha256) is str and len(expected_sha256) == 64
                and sha256(raw).hexdigest() == expected_sha256, 'BOOTSTRAP_PIN_MISMATCH')
        bundle = parse(raw)
        if bundle.get('schema') == 'arms.certified-native-history.v1':
            from backend.market_data.native_historical_bootstrap_v1 import certify_native_history
            return certify_native_history(bundle, expected_sha256)
        require(set(bundle) == {'schema','authored_sha256','segments'} and bundle['schema'] == SCHEMA
                and bundle['authored_sha256'] == AUTHORED_SHA256, 'BOOTSTRAP_AUTHORED_IDENTITY')
        require(type(bundle['segments']) is list and 0 < len(bundle['segments']) <= 128, 'BOOTSTRAP_SEGMENTS')
        bars, sessions, gaps = [], [], 0
        for segment in bundle['segments']:
            session, values = _segment(segment)
            require(session not in sessions, 'BOOTSTRAP_DUPLICATE_SESSION')
            sessions.append(session)
            if bars:
                delta = ticks(values[0].label)-ticks(bars[-1].label)
                require(delta > 0, 'BOOTSTRAP_OVERLAP_OR_ORDER')
                gaps += int(delta != MINUTE)
            bars.extend(values)
            require(len(bars) <= MAX_BARS, 'BOOTSTRAP_BAR_LIMIT')
        return CertifiedBootstrap(expected_sha256, tuple(bars), tuple(sessions), gaps)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError):
        raise ValueError('BOOTSTRAP_MALFORMED') from None
