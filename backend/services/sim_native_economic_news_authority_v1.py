"""SIM_NATIVE news only. HMAC proves ARMS issuance, never vendor truth.

V1 binds inclusive +/-300s blackouts to NEWS_POLICY_ID without changing the
global commissioning policy. Coverage intervals certify completeness, including
explicitly empty calendars; metadata alone does not establish external truth.

Only the explicit operator publisher writes packages/history. Every lookup
reauthenticates both. The protected history is the durable rollback floor and
must never be restored independently or discarded to renew authority. Restoring
the entire authority store requires separate operator recovery/certification.
No lexical ordering: issued_us strictly increases, versions cannot be reused
with different content, and only the latest recorded digest can be consumed.
"""
import hashlib
import hmac
import re
import subprocess

from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_admission_envelope_v3 import utc_us
from backend.services.sim_native_market_hours_authority_v1 import (
    canonical, parse, require, read_bounded, identity as base_identity)

SCHEMA = 'ARMS_SIM_NATIVE_ECONOMIC_NEWS_AUTHORITY_V1'
DOMAIN = b'arms.sim-native.economic-news.v1\0'
HISTORY_DOMAIN = b'arms.sim-native.economic-news.history.v1\0'
MAX_LIFE_US = 86_400_000_000
BEFORE = AFTER = 300
NEWS_POLICY_ID = hashlib.sha256(canonical(dict(schema=SCHEMA, version=1,
    blackout_before_seconds=BEFORE, blackout_after_seconds=AFTER,
    boundaries='INCLUSIVE', impact='HIGH', currency='USD', max_life_us=MAX_LIFE_US))).hexdigest()
EVENT_FIELDS = set('event_id name event_us impact currency'.split())
FIELDS = set(('schema version backend_account_id execution_domain native_account provider instrument '
    'instrument_root runtime_generation risk_version risk_profile authority_id configuration_generation '
    'commissioning_policy_id news_policy_id snapshot_version source_name source_reference source_sha256 '
    'generated_us issued_us expires_us coverage_start_us coverage_end_us coverage_intervals '
    'blackout_before_seconds blackout_after_seconds high_impact_events').split())
HISTORY_SCHEMA = 'ARMS_SIM_NATIVE_ECONOMIC_NEWS_HISTORY_V1'
FILES = ('economic-news-v1.json', 'economic-news-v1.sig', 'economic-news-history-v1.json')
LOCK = 'economic-news-publish.lock'


def identity(config, policy_id, key):
    return dict(base_identity(config, policy_id, key), risk_profile='TOPSTEP_150K', news_policy_id=NEWS_POLICY_ID)


def sign(payload, key, domain=DOMAIN):
    return hmac.new(key, domain+payload, hashlib.sha256).hexdigest().encode('ascii')


def _text(value):
    return type(value) is str and 0 < len(value) <= 512 and value.strip() == value and all(32 <= ord(c) < 127 for c in value)


def _identifier(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value) is not None


def _hash(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def verify(payload, signature, *, config, policy_id, key, now):
    require(type(signature) is bytes and hmac.compare_digest(signature, sign(payload,key)), 'HMAC_INVALID')
    v = parse(payload)
    require(type(v) is dict and set(v) == FIELDS and canonical(v) == payload, 'PACKAGE_SCHEMA')
    require(v['schema'] == SCHEMA and type(v['version']) is int and v['version'] == 1, 'PACKAGE_VERSION')
    require(all(type(v[k]) is type(x) and v[k] == x for k,x in identity(config,policy_id,key).items()), 'PACKAGE_BINDING')
    require(type(v['blackout_before_seconds']) is int and v['blackout_before_seconds'] == BEFORE
            and type(v['blackout_after_seconds']) is int and v['blackout_after_seconds'] == AFTER, 'NEWS_POLICY_MISMATCH')
    require(_identifier(v['snapshot_version']), 'SNAPSHOT_VERSION')
    require(_text(v['source_name']) and _text(v['source_reference']) and _hash(v['source_sha256']), 'SOURCE_METADATA')
    times = ('generated_us','issued_us','expires_us','coverage_start_us','coverage_end_us')
    require(all(type(v[k]) is int and 0 < v[k] <= 253402300799999999 for k in times), 'PACKAGE_TIME')
    now_us = utc_us(now)
    require(v['generated_us'] <= v['issued_us'] <= now_us, 'FUTURE_PACKAGE')
    require(0 < v['expires_us']-v['issued_us'] <= MAX_LIFE_US, 'PACKAGE_LIFETIME')
    require(v['coverage_start_us'] <= v['coverage_end_us'] and v['expires_us'] <= v['coverage_end_us'], 'COVERAGE_INVALID')
    require(now_us < v['expires_us'], 'EXPIRED')
    intervals = v['coverage_intervals']
    require(type(intervals) is list and 0 < len(intervals) <= 128, 'COVERAGE_INVALID')
    prior = None
    for interval in intervals:
        require(type(interval) is dict and set(interval) == {'start_us','end_us'}, 'COVERAGE_INVALID')
        a,b = interval['start_us'],interval['end_us']
        require(type(a) is int and type(b) is int and v['coverage_start_us'] <= a <= b <= v['coverage_end_us']
                and (prior is None or a > prior), 'COVERAGE_INVALID')
        prior = b
    require(intervals[0]['start_us'] == v['coverage_start_us'] and intervals[-1]['end_us'] == v['coverage_end_us'], 'COVERAGE_INVALID')
    events = v['high_impact_events']
    require(type(events) is list and len(events) <= 1024, 'EVENT_SCHEMA')
    ids, identities = set(), set()
    for event in events:
        require(type(event) is dict and set(event) == EVENT_FIELDS, 'EVENT_SCHEMA')
        require(_identifier(event['event_id']) and _text(event['name']) and event['impact'] == 'HIGH'
                and event['currency'] == 'USD' and type(event['event_us']) is int, 'EVENT_SCHEMA')
        require(covered(v,event['event_us']), 'EVENT_OUTSIDE_COVERAGE')
        event_identity = (event['event_us'],event['name'],event['currency'])
        require(event['event_id'] not in ids and event_identity not in identities, 'EVENT_CONFLICT')
        ids.add(event['event_id']);identities.add(event_identity)
    return v


def covered(value, at):
    return any(row['start_us'] <= at <= row['end_us'] for row in value['coverage_intervals'])


def history_wire(history, key):
    raw = canonical(history)
    return canonical(dict(history=history, signature=sign(raw,key,HISTORY_DOMAIN).decode('ascii')))


def verify_history(raw, *, config, policy_id, key):
    envelope = parse(raw)
    require(type(envelope) is dict and set(envelope) == {'history','signature'} and canonical(envelope) == raw, 'HISTORY_INVALID')
    h = envelope['history']
    require(type(envelope['signature']) is str and hmac.compare_digest(envelope['signature'].encode('ascii'),
        sign(canonical(h),key,HISTORY_DOMAIN)), 'HISTORY_INVALID')
    require(type(h) is dict and set(h) == {'schema','identity','entries'} and h['schema'] == HISTORY_SCHEMA
            and h['identity'] == identity(config,policy_id,key), 'HISTORY_INVALID')
    require(type(h['entries']) is list and 0 < len(h['entries']) <= 512, 'HISTORY_INVALID')
    prior, versions = 0, set()
    for row in h['entries']:
        require(type(row) is dict and set(row) == {'snapshot_version','issued_us','sha256'}, 'HISTORY_INVALID')
        require(_identifier(row['snapshot_version']) and row['snapshot_version'] not in versions
                and type(row['issued_us']) is int and row['issued_us'] > prior and _hash(row['sha256']), 'HISTORY_INVALID')
        prior = row['issued_us'];versions.add(row['snapshot_version'])
    return h


def entry(value, payload):
    return dict(snapshot_version=value['snapshot_version'],issued_us=value['issued_us'],sha256=hashlib.sha256(payload).hexdigest())


class SimNativeEconomicNewsLifecycleV1:
    """Pure lookups; no environment/PAPER fallback, refresh, or durable writes."""
    def __init__(self, *, context, clock):
        self.context, self.clock = context, clock

    @staticmethod
    def unavailable(status='UNAVAILABLE', reason='AUTHORITY_UNAVAILABLE'):
        return dict(status=status, reason=reason, covered=False, blocked=True,
            package_age_seconds=None, coverage_start=None, coverage_end=None, expires_us=None,
            next_event_us=None, news_policy_id=NEWS_POLICY_ID)

    def inspect(self, *, symbol='NQ', timestamp=None):
        try:
            root = auth.authority_root()/'authority-inputs'
            require(not (root/LOCK).exists(), 'PUBLICATION_IN_PROGRESS')
            payload, signature, history_raw = [read_bounded(root/name) for name in FILES]
            key = auth.load_authority()
            config, policy_id = self.context(self.clock())
            now = self.clock()  # No stale pre-I/O time grants authority.
            v = verify(payload,signature,config=config,policy_id=policy_id,key=key,now=now)
            h = verify_history(history_raw,config=config,policy_id=policy_id,key=key)
            require(h['entries'][-1] == entry(v,payload), 'ROLLBACK_OR_CONFLICT')
            # A publication concurrent with this lookup must not mix generations.
            require(not (root/LOCK).exists() and history_raw == read_bounded(root/FILES[2]), 'PUBLICATION_CHANGED')
            now_us = utc_us(self.clock())
            require(now_us >= utc_us(now), 'CLOCK_REGRESSION')
            require(v['issued_us'] <= now_us < v['expires_us'], 'EXPIRED')
            at = now_us if timestamp is None else utc_us(timestamp)
            require(symbol in ('NQ','MNQ'), 'UNSUPPORTED_SYMBOL')
            require(v['issued_us'] <= at <= now_us and at < v['expires_us'], 'EVALUATION_TIME')
            # Admission samples its time before I/O. Neither an old caller time
            # nor a slow read may cross into a gap/blackout and still grant CLEAR.
            in_coverage = covered(v,at) and covered(v,now_us)
            blocked = not in_coverage or any(e['event_us']-BEFORE*1_000_000 <= t <= e['event_us']+AFTER*1_000_000
                for e in v['high_impact_events'] for t in (at,now_us))
            status = ('OUTSIDE_CERTIFIED_COVERAGE' if not in_coverage else 'HIGH_IMPACT_BLOCK' if blocked else 'CERTIFIED_CLEAR')
            return dict(status=status,reason=None if not blocked else status,covered=in_coverage,blocked=blocked,
                package_age_seconds=(now_us-v['issued_us'])/1_000_000,coverage_start=v['coverage_start_us'],
                coverage_end=v['coverage_end_us'],expires_us=v['expires_us'],news_policy_id=NEWS_POLICY_ID,
                snapshot_version=v['snapshot_version'],next_event_us=min((e['event_us'] for e in v['high_impact_events'] if e['event_us'] >= at),default=None))
        except FileNotFoundError:
            return self.unavailable('PACKAGE_REQUIRED','PACKAGE_MISSING')
        except (ValueError, OSError, TypeError, KeyError, OverflowError, AttributeError, RuntimeError, subprocess.SubprocessError) as error:
            known = {'EXPIRED','FUTURE_PACKAGE','ROLLBACK_OR_CONFLICT','PUBLICATION_IN_PROGRESS','PUBLICATION_CHANGED',
                     'EVALUATION_TIME','UNSUPPORTED_SYMBOL','CLOCK_REGRESSION'}
            reason = str(error) if str(error) in known else 'AUTHORITY_INVALID'
            return self.unavailable('EXPIRED' if reason == 'EXPIRED' else 'UNAVAILABLE',reason)

    def get_snapshot(self):
        return self.inspect()

    def get_active_provider(self):
        return self

    def get_economic_news_authority(self):
        return self

    def is_news_blocked(self, *, symbol, timestamp):
        return self.inspect(symbol=symbol,timestamp=timestamp)['blocked']
