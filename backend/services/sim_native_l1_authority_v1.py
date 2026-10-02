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

from backend.market_data.fresh_native_adapter_v1 import MAX_L1_FILE, _Tail, local_path
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
        self.tail = self.session = self.directory_identity = None
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
                    and type(p['reason']) is str, 'TERMINAL_SCHEMA')
            raise ValueError('STREAM_TERMINATED')
        else:
            raise ValueError('FRAME_KIND')
        self.sequence, self.last_raw, self.last_event = v['sequence'], raw, at

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
                files = sorted(directory.glob('*.l1.jsonl'))
                require(len(files) <= 1, 'MULTIPLE_SESSIONS')
                if not files:
                    require(self.session is None, 'STREAM_REMOVED')
                    return
                path = private_path(files[0])
                session = path.name.removesuffix('.l1.jsonl')
                require(str(UUID(session)) == session and self.session in (None,session), 'SESSION_CHANGED')
                if self.tail is None:
                    self.session, self.tail = session, _Tail(path, max_file=L1_STREAM_MAX_BYTES)
                    self.status = 'WAITING_FOR_HELLO'
                # Retain the batch boundary for both publication and pure inspection.
                self.observed_size = path.stat().st_size
                rows = self.tail.read(tick)
                # Concurrent appends may be newer than the poll-start sample.
                # Bound this batch strictly by a clock sampled after its bytes.
                post_now, post_tick = self.clock(), self.elapsed()
                require(post_now >= now and post_tick >= tick, 'CLOCK_REGRESSION')
                now, tick = post_now, post_tick
                for raw, _, _ in rows:
                    self._frame(raw, now)
                # Never publish a valid prefix of an incomplete or unchecked batch.
                self.last_poll_elapsed = tick
                self.last_poll_wall = now
                require(self.tail.partial_since is None or tick-self.tail.partial_since <= 5, 'PARTIAL_TIMEOUT')
                if self.tail.partial or self.tail.offset < self.observed_size:
                    return
                if self.heartbeat is not None:
                    require(0 <= (now-self.heartbeat).total_seconds() <= HEARTBEAT, 'HEARTBEAT_TIMEOUT')
                elif (now-self.started).total_seconds() > HEARTBEAT:
                    raise ValueError('HELLO_TIMEOUT')
                if self.quote is not None:
                    self.quote_age = (now-self.quote['timestamp']).total_seconds()
                    self.quote_elapsed = tick
                    RuntimeQuoteAuthorityV2.publish_quote(self.quotes, **self.quote)
            except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError):
                self.revoke('STREAM_OR_CONTEXT_INVALID')

    def _unchanged(self):
        directory, identity = self._directory()
        require(identity == self.directory_identity, 'DIRECTORY_CHANGED')
        files = list(directory.glob('*.l1.jsonl'))
        require(len(files) == 1 and files[0] == self.tail.path, 'SESSION_CHANGED')
        path = local_path(self.tail.path)
        info = path.stat()
        require((info.st_dev,info.st_ino) == self.tail.identity
                and info.st_size >= self.tail.offset >= self.observed_size
                and not self.tail.partial, 'UNVALIDATED_STREAM')
        with _Tail._open_read(path) as handle:
            require(sha256(handle.read(self.tail.offset)).digest() == self.tail.digest.digest(), 'PREFIX_CHANGED')

    def inspect(self):
        """Pure read: no ingestion, publication, latch changes or filesystem writes."""
        with self.lock:
            view = dict(status=self.status, reason=self.reason, provider=IDENTITY['provider'], instrument='NQ',
                contract=IDENTITY['contract'], session=self.session, sequence=self.sequence,
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
