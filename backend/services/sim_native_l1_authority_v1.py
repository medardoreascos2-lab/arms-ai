"""Single-session local native L1 reader; no HTTP publication or execution.

The private operator-owned directory is the source trust boundary, not a native
digital signature. Any discontinuity latches until explicit service restart and
a new exporter session. Existing market-hours/news authorities are untouched.
"""
from datetime import datetime
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re
from threading import RLock
from time import monotonic
from uuid import UUID

from backend.market_data.fresh_native_adapter_v1 import (
    MAX_L1_FILE, _Tail, _exact_prefix_digest, local_path,
)
from backend.services import sim_native_authority_v3 as auth
from backend.services.sim_native_market_hours_authority_v1 import private_path, parse, require
from backend.services.runtime_quote_authority_v2 import RuntimeQuoteAuthorityV2
from backend.services.runtime_spread_authority_v2 import RuntimeSpreadAuthorityV2

IDENTITY = dict(provider='Provider31', contract='NQ DEC26', instrument='NQ', expiry='2026-12-01',
    tick_size=.25, point_value=20, application_timezone='UTC',
    trading_hours_template='CME US Index Futures ETH', realtime=True, read_only=True, level=1)
FIELDS = set('schema session sequence event_time kind payload'.split())
MAX_AGE = 30
HEARTBEAT = 15
L1_STREAM_MAX_BYTES = MAX_L1_FILE
L1_MANIFEST_MAX_BYTES = 200_000
MANIFEST_FIELDS = {'schema','session','provider','instrument','contract',
    'segment_capacity_bytes','state','terminal_reason','segments'}
SEGMENT_FIELDS = {'index','file','first_sequence','last_sequence','bytes','sha256','sealed'}


def utc(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,7})?Z', value), 'UTC_REQUIRED')
    return datetime.fromisoformat(value)


class _NativeQuotes(RuntimeQuoteAuthorityV2):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def publish_quote(self, **kwargs):
        raise RuntimeError('NATIVE_READER_IS_ONLY_PUBLISHER')

    def get_quote(self, *, symbol):
        with self.owner.lock:
            if symbol != 'NQ' or self.owner.inspect()[1] is None:
                return None
            return super().get_quote(symbol=symbol)


class SimNativeL1AuthorityV1:
    def __init__(self, *, admission, context, clock, directory=None, elapsed=monotonic):
        require(admission.settings.maximum_quote_age_seconds == MAX_AGE
                and admission.settings.maximum_spread_points == 5, 'COMMISSIONING_POLICY_CHANGED')
        self.admission, self.context, self.clock, self.elapsed = admission, context, clock, elapsed
        self.directory = Path(directory) if directory is not None else auth.authority_root()/'l1-stream'
        self.lock = RLock()
        self.started, self.started_elapsed = clock(), elapsed()
        self.last_poll_elapsed = self.started_elapsed
        self.last_poll_wall = self.started
        self.status, self.reason = 'WAITING_FOR_STREAM', None
        self.validation_error = None
        self.tail = self.session = self.directory_identity = None
        self.manifest_path = self.manifest_sha256 = self.manifest = None
        self.segment_index = 0
        self.sealed_segments = {}
        self.terminal_reason = None
        self.observed_size = 0
        self.sequence = -1
        self.last_raw = self.last_event = self.quote = self.heartbeat = None
        self.quote_elapsed = self.quote_age = None
        self.quotes = _NativeQuotes(self)
        admission.quote_authority = self.quotes
        admission.runtime_spread_authority = RuntimeSpreadAuthorityV2(quote_authority=self.quotes,
            spread_authority=admission.spread_authority, maximum_quote_age_seconds=MAX_AGE)

    def revoke(self, reason):
        self.status, self.reason, self.quote = 'REVOKED', reason, None
        if self.tail is not None:
            self.tail.close()
            self.tail = None

    def _directory(self):
        directory = private_path(self.directory)
        info = directory.stat()
        require(info.st_ino != 0 and directory.is_dir(), 'DIRECTORY_IDENTITY')
        identity = (info.st_dev, info.st_ino)
        require(self.directory_identity in (None, identity), 'DIRECTORY_REPLACED')
        return directory, identity

    def _frame(self, raw, now):
        v = parse(raw)
        require(type(v) is dict and set(v) == FIELDS and v['schema'] == 'arms.nt.l1.v1'
                and v['session'] == self.session, 'FRAME_IDENTITY')
        require(type(v['sequence']) is int and v['sequence'] >= 0, 'SEQUENCE')
        if v['sequence'] == self.sequence:
            require(raw == self.last_raw, 'REPLAY_CONFLICT')
            return  # Exact adjacent retransmission neither renews quote nor liveness.
        require(v['sequence'] == self.sequence+1, 'SEQUENCE_GAP_OR_ROLLBACK')
        at = utc(v['event_time'])
        require(at <= now and at >= self.started and (self.last_event is None or at >= self.last_event), 'EVENT_TIME')
        p, kind = v['payload'], v['kind']
        require(type(p) is dict, 'PAYLOAD')
        if self.sequence == -1:
            require(kind == 'HELLO' and set(p) == set(IDENTITY)
                and all(type(p[k]) is type(x) and p[k] == x for k,x in IDENTITY.items()), 'HELLO_IDENTITY')
            self.status = 'AWAITING_TWO_SIDED_QUOTE'
            self.heartbeat = at
        elif kind == 'QUOTE':
            require(set(p) == {'bid','ask','bid_time','ask_time'}, 'QUOTE_SCHEMA')
            require(all(type(p[k]) in (int,float) and isfinite(p[k]) and p[k]>0 for k in ('bid','ask'))
                    and p['ask'] >= p['bid'], 'INVALID_QUOTE')
            bid_at, ask_at = utc(p['bid_time']), utc(p['ask_time'])
            require(self.started <= min(bid_at,ask_at) <= max(bid_at,ask_at) <= at
                and max(bid_at,ask_at) == at and (at-min(bid_at,ask_at)).total_seconds() <= MAX_AGE, 'SIDE_TIME')
            if self.quote is not None:
                require(min(bid_at,ask_at) >= self.quote['timestamp'], 'QUOTE_TIME_REGRESSION')
            self.quote = dict(symbol='NQ',bid=p['bid'],ask=p['ask'],timestamp=min(bid_at,ask_at))
            self.status = 'FRESH'
        elif kind == 'HEARTBEAT':
            require(p == {'connected':True} and p['connected'] is True, 'CONNECTION_STATE')
            self.heartbeat = at
        elif kind == 'TERMINAL':
            require(set(p) == {'connected','reason'} and p['connected'] is False
                    and type(p['reason']) is str and p['reason'], 'TERMINAL_SCHEMA')
            require(self.terminal_reason is None, 'DUPLICATE_TERMINAL')
            self.terminal_reason = p['reason']
            self.quote = None
        else:
            raise ValueError('FRAME_KIND')
        self.sequence, self.last_raw, self.last_event = v['sequence'], raw, at

    def _read_manifest(self, directory):
        manifests = sorted(directory.glob('*.l1.manifest.json'))
        legacy = sorted(path for path in directory.glob('*.l1.jsonl')
            if '.segment.' not in path.name)
        require(len(manifests) <= 1, 'MULTIPLE_MANIFESTS')
        require(not manifests or not legacy, 'LEGACY_AND_SEGMENTED_STREAMS')
        if not manifests:
            require(not list(directory.glob('*.segment.*.l1.jsonl')), 'MANIFEST_MISSING')
            return None
        path = private_path(manifests[0])
        raw = path.read_bytes()
        require(0 < len(raw) <= L1_MANIFEST_MAX_BYTES, 'MANIFEST_SIZE')
        value = parse(raw)
        require(type(value) is dict and set(value) == MANIFEST_FIELDS
            and value['schema'] == 'arms.nt.l1.manifest.v1', 'MANIFEST_SCHEMA')
        session = value['session']
        require(type(session) is str and str(UUID(session)) == session, 'MANIFEST_SESSION')
        require(value['provider'] == IDENTITY['provider']
            and value['instrument'] == IDENTITY['instrument']
            and value['contract'] == IDENTITY['contract'], 'MANIFEST_IDENTITY')
        require(type(value['segment_capacity_bytes']) is int
            and value['segment_capacity_bytes'] == L1_STREAM_MAX_BYTES, 'MANIFEST_CAPACITY')
        state, terminal = value['state'], value['terminal_reason']
        require(state in ('ACTIVE','TERMINATED'), 'MANIFEST_STATE')
        require((state == 'ACTIVE' and terminal is None)
            or (state == 'TERMINATED' and type(terminal) is str and terminal),
            'MANIFEST_TERMINAL')
        segments = value['segments']
        require(type(segments) is list and 0 < len(segments) <= 4096, 'MANIFEST_SEGMENTS')
        previous_last = -1
        names = []
        for expected, item in enumerate(segments, 1):
            require(type(item) is dict and set(item) == SEGMENT_FIELDS, 'SEGMENT_SCHEMA')
            name = session + '.segment.' + str(expected).zfill(6) + '.l1.jsonl'
            require(type(item['index']) is int and item['index'] == expected
                and item['file'] == name, 'SEGMENT_ORDER')
            require(type(item['first_sequence']) is int
                and item['first_sequence'] == previous_last + 1, 'SEGMENT_SEQUENCE_START')
            sealed = item['sealed']
            require(type(sealed) is bool, 'SEGMENT_SEALED')
            if sealed:
                require(type(item['last_sequence']) is int
                    and item['last_sequence'] >= item['first_sequence']
                    and type(item['bytes']) is int and 0 < item['bytes'] <= L1_STREAM_MAX_BYTES
                    and type(item['sha256']) is str
                    and re.fullmatch(r'[0-9a-f]{64}', item['sha256']) is not None,
                    'SEGMENT_SEAL')
                previous_last = item['last_sequence']
            else:
                require(expected == len(segments) and state == 'ACTIVE'
                    and item['last_sequence'] is None and item['bytes'] is None
                    and item['sha256'] is None, 'ACTIVE_SEGMENT_POSITION')
                previous_last = item['first_sequence'] - 1
            names.append(name)
        require((state == 'ACTIVE' and segments[-1]['sealed'] is False)
            or (state == 'TERMINATED' and all(item['sealed'] for item in segments)),
            'MANIFEST_COMPLETION')
        actual = sorted(path.name for path in directory.glob('*.segment.*.l1.jsonl'))
        require(actual == names, 'SEGMENT_SET')
        if self.manifest is not None:
            old = self.manifest
            require(all(value[key] == old[key] for key in
                ('schema','session','provider','instrument','contract','segment_capacity_bytes')),
                'MANIFEST_IDENTITY_CHANGED')
            require(len(segments) in (len(old['segments']), len(old['segments']) + 1),
                'MANIFEST_SEGMENT_SKIP')
            for index, prior in enumerate(old['segments']):
                current = segments[index]
                if prior['sealed']:
                    require(current == prior, 'SEALED_SEGMENT_MUTATED')
                else:
                    require(current['index'] == prior['index']
                        and current['file'] == prior['file']
                        and current['first_sequence'] == prior['first_sequence'],
                        'ACTIVE_SEGMENT_REPLACED')
        return path, raw, value

    def _poll_segmented(self, directory, manifest_record, now, tick):
        manifest_path, manifest_raw, manifest = manifest_record
        session = manifest['session']
        require(self.session in (None, session), 'SESSION_CHANGED')
        self.session = session
        segments = manifest['segments']
        while self.segment_index < len(segments):
            item = segments[self.segment_index]
            path = private_path(directory / item['file'])
            if self.tail is None:
                require(item['first_sequence'] == self.sequence + 1, 'SEGMENT_SEQUENCE_BOUNDARY')
                self.tail = _Tail(path, max_file=L1_STREAM_MAX_BYTES)
                if self.sequence == -1:
                    self.status = 'WAITING_FOR_HELLO'
            require(self.tail.path == path, 'SEGMENT_PATH_CHANGED')
            info = path.stat()
            if item['sealed']:
                require(info.st_size == item['bytes'], 'SEALED_SEGMENT_SIZE')
            else:
                require(info.st_size <= L1_STREAM_MAX_BYTES, 'ACTIVE_SEGMENT_SIZE')
            self.observed_size = info.st_size
            rows = self.tail.read(tick)
            post_now, post_tick = self.clock(), self.elapsed()
            require(post_now >= now and post_tick >= tick, 'CLOCK_REGRESSION')
            now, tick = post_now, post_tick
            for raw, _, _ in rows:
                require(self.terminal_reason is None, 'FRAME_AFTER_TERMINAL')
                self._frame(raw, now)
            require(self.tail.partial_since is None
                or tick-self.tail.partial_since <= 5, 'PARTIAL_TIMEOUT')
            if self.tail.partial or self.tail.offset < self.observed_size:
                self.manifest_path = manifest_path
                self.manifest_sha256 = sha256(manifest_raw).hexdigest()
                self.manifest = manifest
                return now, tick, False
            if not item['sealed']:
                break
            require(self.tail.offset == item['bytes']
                and self.sequence == item['last_sequence']
                and self.tail.digest.hexdigest() == item['sha256'], 'SEGMENT_SEAL_MISMATCH')
            self.sealed_segments[item['index']] = (
                info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, item['sha256'])
            self.tail.close()
            self.tail = None
            self.segment_index += 1
        self.manifest_path = manifest_path
        self.manifest_sha256 = sha256(manifest_raw).hexdigest()
        self.manifest = manifest
        if manifest['state'] == 'TERMINATED':
            require(self.segment_index == len(segments) and self.terminal_reason is not None
                and self.terminal_reason == manifest['terminal_reason'], 'TERMINAL_REASON_MISMATCH')
            self.revoke('L1_STREAM_TERMINATED:' + self.terminal_reason)
            return now, tick, False
        if self.terminal_reason is not None:
            # The terminal frame can become visible just before the exporter's
            # atomic final-manifest replacement. Revoke from the validated frame
            # immediately; never expose the prior FRESH state for another poll.
            self.revoke('L1_STREAM_TERMINATED:' + self.terminal_reason)
            return now, tick, False
        return now, tick, True

    def poll(self):
        """Lifespan worker only; validate the entire observed batch before publication."""
        with self.lock:
            if self.status == 'REVOKED':
                return
            try:
                now, tick = self.clock(), self.elapsed()
                require(tick >= self.last_poll_elapsed and now >= self.last_poll_wall, 'CLOCK_REGRESSION')
                self.context()  # Current authenticated SIM_NATIVE configuration.
                try:
                    directory, identity = self._directory()
                except FileNotFoundError:
                    require(self.directory_identity is None, 'DIRECTORY_REMOVED')
                    return
                self.directory_identity = identity
                manifest_record = self._read_manifest(directory)
                if manifest_record is not None:
                    now, tick, ready = self._poll_segmented(
                        directory, manifest_record, now, tick)
                    self.last_poll_elapsed = tick
                    self.last_poll_wall = now
                    if self.status == 'REVOKED' or not ready:
                        return
                else:
                    files = sorted(directory.glob('*.l1.jsonl'))
                    require(len(files) <= 1, 'MULTIPLE_SESSIONS')
                    if not files:
                        require(self.session is None, 'STREAM_REMOVED')
                        return
                    path = private_path(files[0])
                    session = path.name.removesuffix('.l1.jsonl')
                    require(str(UUID(session)) == session
                        and self.session in (None,session), 'SESSION_CHANGED')
                    if self.tail is None:
                        self.session, self.tail = session, _Tail(
                            path, max_file=L1_STREAM_MAX_BYTES)
                        self.status = 'WAITING_FOR_HELLO'
                    self.observed_size = path.stat().st_size
                    rows = self.tail.read(tick)
                    post_now, post_tick = self.clock(), self.elapsed()
                    require(post_now >= now and post_tick >= tick, 'CLOCK_REGRESSION')
                    now, tick = post_now, post_tick
                    for raw, _, _ in rows:
                        require(self.terminal_reason is None, 'FRAME_AFTER_TERMINAL')
                        self._frame(raw, now)
                # Never publish a valid prefix of an incomplete or unchecked batch.
                self.last_poll_elapsed = tick
                self.last_poll_wall = now
                require(self.tail.partial_since is None or tick-self.tail.partial_since <= 5, 'PARTIAL_TIMEOUT')
                if self.tail.partial or self.tail.offset < self.observed_size:
                    return
                if self.terminal_reason is not None:
                    self.revoke('L1_STREAM_TERMINATED:' + self.terminal_reason)
                    return
                if self.heartbeat is not None:
                    require(0 <= (now-self.heartbeat).total_seconds() <= HEARTBEAT, 'HEARTBEAT_TIMEOUT')
                elif (now-self.started).total_seconds() > HEARTBEAT:
                    raise ValueError('HELLO_TIMEOUT')
                if self.quote is not None:
                    self.quote_age = (now-self.quote['timestamp']).total_seconds()
                    self.quote_elapsed = tick
                    RuntimeQuoteAuthorityV2.publish_quote(self.quotes, **self.quote)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError) as error:
                self.validation_error = type(error).__name__ + ':' + str(error)
                self.revoke('STREAM_OR_CONTEXT_INVALID')

    def _unchanged(self):
        directory, identity = self._directory()
        require(identity == self.directory_identity, 'DIRECTORY_CHANGED')
        if self.manifest_path is not None:
            manifest_path = local_path(self.manifest_path)
            raw = manifest_path.read_bytes()
            require(sha256(raw).hexdigest() == self.manifest_sha256, 'UNVALIDATED_MANIFEST')
            expected = [item['file'] for item in self.manifest['segments']]
            require(sorted(path.name for path in directory.glob('*.segment.*.l1.jsonl'))
                == expected, 'SEGMENT_SET_CHANGED')
            for index, recorded in self.sealed_segments.items():
                path = local_path(directory / self.manifest['segments'][index-1]['file'])
                info = path.stat()
                require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    == recorded[:4], 'SEALED_SEGMENT_CHANGED')
            require(self.tail is not None, 'ACTIVE_SEGMENT_MISSING')
            path = local_path(self.tail.path)
            info = path.stat()
            require((info.st_dev,info.st_ino) == self.tail.identity
                and info.st_size >= self.tail.offset >= self.observed_size
                and not self.tail.partial, 'UNVALIDATED_STREAM')
            with _Tail._open_read(path) as handle:
                require(_exact_prefix_digest(handle, self.tail.offset)
                    == self.tail.digest.digest(), 'PREFIX_CHANGED')
            return
        files = list(directory.glob('*.l1.jsonl'))
        require(len(files) == 1 and files[0] == self.tail.path, 'SESSION_CHANGED')
        path = local_path(self.tail.path)
        info = path.stat()
        require((info.st_dev,info.st_ino) == self.tail.identity
                and info.st_size >= self.tail.offset >= self.observed_size
                and not self.tail.partial, 'UNVALIDATED_STREAM')
        with _Tail._open_read(path) as handle:
            require(_exact_prefix_digest(handle, self.tail.offset)
                == self.tail.digest.digest(), 'PREFIX_CHANGED')

    def inspect(self):
        """Pure read: no ingestion, publication, latch changes or filesystem writes."""
        with self.lock:
            view = dict(status=self.status, reason=self.reason, provider=IDENTITY['provider'], instrument='NQ',
                contract=IDENTITY['contract'], session=self.session, sequence=self.sequence,
                validation_error=self.validation_error,
                bid=None, ask=None, spread_points=None, quote_age_seconds=None,
                maximum_quote_age_seconds=MAX_AGE, observed_at=None)
            if self.status == 'REVOKED' or self.tail is None:
                return view, None
            try:
                self.context()
                self._unchanged()
                now, tick = self.clock(), self.elapsed()
                require(now >= self.last_poll_wall and 0 <= tick-self.last_poll_elapsed <= HEARTBEAT and self.heartbeat is not None
                        and 0 <= (now-self.heartbeat).total_seconds() <= HEARTBEAT, 'LIVENESS')
                if self.quote is None or self.quote_elapsed is None:
                    return view, None
                age = max((now-self.quote['timestamp']).total_seconds(),self.quote_age+tick-self.quote_elapsed)
                require(now >= self.quote['timestamp'] and tick >= self.quote_elapsed, 'CLOCK_REGRESSION')
                view.update(status='FRESH' if age <= MAX_AGE else 'STALE', quote_age_seconds=age,
                    bid=self.quote['bid'], ask=self.quote['ask'], observed_at=self.quote['timestamp'].isoformat(),
                    spread_points=self.admission.spread_authority.resolve_spread_points(**{k:self.quote[k] for k in ('symbol','bid','ask')}))
                return view, self.quote if age <= MAX_AGE else None
            except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError):
                view.update(status='REVOKED',reason='STREAM_OR_CONTEXT_INVALID')
                return view, None

    def get_snapshot(self):
        return self.inspect()[0]

    def close(self):
        with self.lock:
            self.revoke('SERVICE_STOPPED')
