"""Explicit local file tail. Analysis only; no account or execution interface.

File identity + exact pairs bind observations, not cryptographic writer identity.
The deployment boundary is the operator-controlled local exporter directory.
"""
from collections import deque
from hashlib import sha256
from math import isfinite
import os
from pathlib import Path
import stat
from threading import RLock
from uuid import UUID, uuid4

from backend.market_data.analysis_time_profile_v1 import MarketAnalysisTimeProfileV1, EXPORTER_SHA256, require
from tools.native_timing_witness_v1 import IDENTITY, check_pair, ticks, qpc_pair
from tools.production_timing_v1 import PAIR_FIELDS, parse

MAX_FILE = 32 * 1024 * 1024
CHUNK = 65536
MAX_LINE = 16384
MAX_QUEUE = 1024


class WindowsQpc:
    """New process-local epoch every start; no persisted recovery or wall authority."""
    def __init__(self):
        self.epoch = str(uuid4())

    def __call__(self):
        sample = qpc_pair()  # Actual Windows QueryPerformanceCounter, same as Stopwatch.
        return self.epoch, sample['frequency'], sample['qpc_after']


def local_path(path):
    p = Path(path)
    require(p.is_absolute() and not str(p).startswith(('\\\\', '//')), 'LOCAL_ABSOLUTE_PATH_REQUIRED')
    for part in (p, *p.parents):
        if part.exists():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024,
                    'REPARSE_PATH_FORBIDDEN')
    if os.name == 'nt':
        import ctypes
        get_type = ctypes.WinDLL('kernel32', use_last_error=True).GetDriveTypeW
        get_type.argtypes = [ctypes.c_wchar_p]
        get_type.restype = ctypes.c_uint
        require(get_type(p.anchor) == 3, 'LOCAL_FIXED_DRIVE_REQUIRED')
    return p


class _Tail:
    def __init__(self, path):
        self.path = local_path(path)
        self.handle = self._open_read(self.path)
        info = os.fstat(self.handle.fileno())
        self.identity = (info.st_dev, info.st_ino)
        require(info.st_ino and stat.S_ISREG(info.st_mode), 'FILE_IDENTITY_UNAVAILABLE')
        require(info.st_size <= MAX_FILE, 'FILE_LIMIT')
        self.cursor = info.st_size
        self.offset = 0
        self.digest = sha256()
        self.partial = b''
        self.partial_since = None

    @staticmethod
    def _open_read(path):
        if os.name != 'nt':
            return path.open('rb', buffering=0)
        import ctypes
        import msvcrt
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                           ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        create.restype = ctypes.c_void_p
        # Read access only; permit the exporter to write and permit detectable replacement.
        handle = create(str(path), 0x80000000, 7, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            raise OSError('READ_HANDLE_UNAVAILABLE')
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        except Exception:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(handle)
            raise
        return os.fdopen(fd, 'rb', buffering=0)

    def read(self, now):
        info = local_path(self.path).stat()
        require((info.st_dev, info.st_ino) == self.identity, 'FILE_REPLACED')
        require(self.offset <= info.st_size <= MAX_FILE, 'FILE_TRUNCATED_OR_LIMIT')
        # Verify the consumed prefix too: same-inode overwrite must not go unnoticed.
        self.handle.seek(0)
        prefix = self.handle.read(self.offset)
        require(len(prefix) == self.offset and sha256(prefix).digest() == self.digest.digest(), 'PREFIX_CHANGED')
        data = self.handle.read(min(CHUNK, info.st_size-self.offset))
        start = self.offset-len(self.partial)
        self.offset += len(data)
        self.digest.update(data)
        fragments = (self.partial+data).split(b'\n')
        self.partial = fragments.pop()
        rows = []
        for line in fragments:
            require(0 < len(line) <= MAX_LINE, 'LINE_SIZE')
            raw = line[:-1] if line.endswith(b'\r') else line
            require(b'\r' not in raw and bool(raw), 'MALFORMED_LINE')
            rows.append((raw, start, now))
            start += len(line)+1
        require(len(self.partial) <= MAX_LINE, 'PARTIAL_LINE_SIZE')
        if not self.partial:
            self.partial_since = None
        elif self.partial_since is None or fragments:
            self.partial_since = now
        return rows

    def close(self):
        self.handle.close()


class FreshNativeAdapterV1:
    def __init__(self, *, directory, qpc_clock, installed_exporter,
                 heartbeat_seconds=15, processing_seconds=90, pair_wait_seconds=5,
                 startup_seconds=900):
        self.directory = local_path(directory)
        require(self.directory.is_dir(), 'DIRECTORY_REQUIRED')
        source = local_path(installed_exporter)
        require(sha256(source.read_text(encoding='utf-8-sig').encode()).hexdigest() == EXPORTER_SHA256,
                'INSTALLED_EXPORTER_MISMATCH')
        require(all(type(v) in (int, float) and isfinite(v) and v > 0 for v in
                    (heartbeat_seconds, processing_seconds, pair_wait_seconds, startup_seconds)), 'AGE_BUDGET')
        # These are local observation cutoffs, not revised absolute timestamp tolerances.
        require(heartbeat_seconds <= 15 and processing_seconds <= 90 and pair_wait_seconds <= 5
                and startup_seconds <= 900, 'BUDGET_WIDENING')
        self.clock = qpc_clock
        self.epoch, self.frequency, self.start = self.clock()
        require(isinstance(self.epoch, str) and bool(self.epoch) and type(self.frequency) is int
                and self.frequency > 0 and type(self.start) is int and self.start >= 0, 'QPC_CONTEXT')
        self.last_now = self.start
        self.heartbeat_ticks = int(heartbeat_seconds*self.frequency)
        self.wait_ticks = int(pair_wait_seconds*self.frequency)
        self.startup_ticks = int(startup_seconds*self.frequency)
        self.options = dict(heartbeat_seconds=heartbeat_seconds, maximum_processing_seconds=processing_seconds)
        self.lock = RLock()
        self.status = 'WAITING'
        self.reason = None
        self.session = None
        self.market = self.timing = None
        self.queue = deque()
        self.pairs = deque()
        self.sequence = self.pair_sequence = -1
        self.hello = None
        self.last_pair = None
        self.last_receipt = None
        self.bootstrap_records = 0
        self.delivered_records = 0
        self.heartbeat = 0
        self.missing_since = None
        self.bootstrap_deadline = None
        self.root_identity = self._directory_identity()
        self.timing_identity = None
        self.profile = self._new_profile(str(uuid4()))

    def _directory_identity(self):
        info = local_path(self.directory).stat()
        return info.st_dev, info.st_ino

    def sample(self):
        epoch, frequency, now = self.clock()
        require(epoch == self.epoch and type(frequency) is int and frequency == self.frequency
                and type(now) is int and now >= self.last_now, 'QPC_EPOCH_OR_REGRESSION')
        self.last_now = now
        return epoch, frequency, now

    def _new_profile(self, session):
        return MarketAnalysisTimeProfileV1(session=session, epoch=self.epoch, frequency=self.frequency,
            reader_start_qpc=self.start, qpc_clock=self.sample, exporter_sha256=EXPORTER_SHA256, **self.options)

    def revoke(self, reason='ADAPTER_STOPPED', *, disconnected=False):
        with self.lock:
            if self.status not in ('REVOKED', 'DISCONNECTED'):
                self.reason = reason
                self.status = 'DISCONNECTED' if disconnected else 'REVOKED'
                self.profile.revoke(reason)
                for tail in (self.market, self.timing):
                    if tail is not None:
                        tail.close()

    def _discover(self, now):
        require(self._directory_identity() == self.root_identity, 'DIRECTORY_REPLACED')
        candidates = sorted(p for p in self.directory.glob('*.jsonl') if not p.name.endswith('.connection.jsonl'))
        require(len(candidates) <= 1, 'SESSION_ROTATION')
        if not candidates:
            require(self.market is None, 'MARKET_FILE_REMOVED')
            require(now-self.start <= self.startup_ticks, 'ACTIVATION_TIMEOUT')
            return
        path = candidates[0]
        session = path.stem
        require(str(UUID(session)) == session, 'SESSION_FILENAME')
        require(self.session is None or session == self.session, 'SESSION_ROTATION')
        if self.market is None:
            self.market = _Tail(path)
            self.session = session
            self.status = 'BOOTSTRAP'
            self.bootstrap_deadline = now+self.startup_ticks
            self.profile = self._new_profile(session)
        folder = self.directory/'timing'
        if folder.exists():
            info = local_path(folder).stat()
            identity = (info.st_dev, info.st_ino)
            require(self.timing_identity is None or self.timing_identity == identity, 'TIMING_DIRECTORY_REPLACED')
            self.timing_identity = identity
            files = list(folder.glob('*.production-timing.jsonl'))
            require(all(p.name == session+'.production-timing.jsonl' for p in files), 'SIDECAR_SESSION_ROTATION')
            sidecar = folder/(session+'.production-timing.jsonl')
            if sidecar.exists() and self.timing is None:
                self.timing = _Tail(sidecar)
            if Path(str(sidecar)+'.done.json').exists() or Path(str(sidecar)+'.done.tmp').exists():
                self.revoke('WRITER_CLOSED', disconnected=True)
        else:
            require(self.timing is None, 'SIDECAR_REMOVED')

    def _wire(self, raw, row, pair):
        require(set(row) == set('schema session sequence event_time kind payload'.split())
                and row['schema'] == 'arms.nt.market.v1' and row['session'] == self.session
                and type(row['sequence']) is int and row['sequence'] == self.sequence+1, 'CANONICAL_SEQUENCE')
        ticks(row['event_time'])
        if row['kind'] in ('CLOSED', 'FORMING'):
            p = parse(pair)
            require(set(p) == PAIR_FIELDS and p['schema'] == 'arms.nt.production-timing.v1', 'PAIR_SCHEMA')
            require(all(type(p[k]) is int for k in ('pair_sequence','canonical_sequence','qpc_frequency',
                'callback_index','bar_index','bars_ago','bars_in_progress','bars_value')), 'PAIR_INTEGER')
            require(p['session'] == self.session and p['canonical_sequence'] == row['sequence']
                    and p['pair_sequence'] == self.pair_sequence+1 and p['kind'] == row['kind']
                    and p['canonical_sha256'] == sha256(raw).hexdigest()
                    and p['source_bar_label'] == row['payload']['bar_time']
                    and p['qpc_frequency'] == self.frequency, 'PAIR_BINDING')
            require(all(p[k] == v for k, v in IDENTITY.items()) and p['state'] == 'Realtime'
                    and p['bars_in_progress'] == 0 and p['first_tick'] is True
                    and p['observation_only'] is True and p['runtime_admission'] is False, 'PAIR_IDENTITY')
            check_pair(p['callback']); check_pair(p['emission'])
            require(p['callback']['qpc_after'] <= p['emission']['qpc_before']
                    and p['emission']['qpc_after'] <= self.last_now
                    and p['emission']['utc'] == row['event_time'], 'PAIR_QPC_ORDER')
            if self.last_pair:
                require(self.last_pair['emission']['qpc_after'] <= p['emission']['qpc_before'], 'QPC_REGRESSION')
                if self.last_pair['callback'] != p['callback']:
                    require(self.last_pair['emission']['qpc_after'] <= p['callback']['qpc_before'], 'CALLBACK_REGRESSION')
            return p
        require(pair is None, 'EXTRA_PAIR')
        if self.sequence == -1:
            require(row['kind'] == 'HELLO', 'HELLO_REQUIRED')
            # Validate historical HELLO metadata in a disposable empty profile.
            probe = self._new_profile(self.session)
            probe.establish_tail_baseline(raw, canonical_sequence=0, pair_sequence=-1)
        else:
            require(row['kind'] == 'HEARTBEAT' and row['payload'] == {'connected': True}
                    and row['payload']['connected'] is True, 'HEARTBEAT_SCHEMA')
        return None

    def poll(self):
        with self.lock:
            if self.status in ('REVOKED', 'DISCONNECTED'):
                return
            try:
                now = self.sample()[2]
                self.heartbeat += 1
                self._discover(now)
                if self.status in ('WAITING', 'DISCONNECTED'):
                    return
                fresh = self.market.read(now)
                receipt = self.sample()[2]
                self.queue.extend((raw, offset, receipt) for raw, offset, _ in fresh)
                if self.timing:
                    fresh = self.timing.read(now)
                    receipt = self.sample()[2]
                    self.pairs.extend((raw, offset, receipt) for raw, offset, _ in fresh)
                now = self.sample()[2]
                require(len(self.queue) <= MAX_QUEUE and len(self.pairs) <= MAX_QUEUE, 'QUEUE_LIMIT')
                for tail in (self.market, self.timing):
                    if tail and tail.partial_since is not None:
                        require(now-tail.partial_since <= self.wait_ticks, 'PARTIAL_LINE_TIMEOUT')
                while self.queue:
                    raw, offset, receipt = self.queue[0]
                    row = parse(raw)
                    if row.get('kind') == 'DISCONNECTED':
                        require(row.get('session') == self.session and row.get('sequence') == self.sequence+1,
                                'TERMINAL_IDENTITY')
                        self.revoke('EXPORTER_DISCONNECTED', disconnected=True)
                        return
                    bar = row.get('kind') in ('CLOSED', 'FORMING')
                    if bar and not self.pairs:
                        if self.missing_since is None:
                            self.missing_since = now
                        require(now-self.missing_since <= self.wait_ticks, 'MISSING_TIMING_PAIR')
                        break
                    paired = self.pairs[0][0] if bar else None
                    pair = self._wire(raw, row, paired)
                    historical = offset < self.market.cursor or (pair and pair['callback']['qpc_before'] < self.start)
                    if self.status == 'BOOTSTRAP' and pair and not historical and row['kind'] == 'FORMING':
                        # Boundary-local warmup: producer may already emit CLOSED at every boundary.
                        self.profile.establish_tail_baseline(self.hello, canonical_sequence=self.sequence,
                                                             pair_sequence=self.pair_sequence)
                        self.status = 'LIVE_TAIL'
                    if self.status == 'LIVE_TAIL':
                        require(not historical, 'OLD_ROW_AFTER_BASELINE')
                        self.profile.accept(raw, paired, receipt_qpc=receipt)
                        self.last_receipt = receipt
                        self.delivered_records += 1
                    else:
                        self.bootstrap_records += 1
                    if row['kind'] == 'HELLO':
                        self.hello = raw
                    self.sequence = row['sequence']
                    if bar:
                        self.pairs.popleft()
                        self.pair_sequence = pair['pair_sequence']
                        self.last_pair = pair
                    self.queue.popleft()
                    self.missing_since = None
                if self.pairs:
                    require(now-self.pairs[0][2] <= self.wait_ticks, 'ORPHAN_TIMING_PAIR')
                if self.status == 'BOOTSTRAP':
                    require(now <= self.bootstrap_deadline, 'BOOTSTRAP_TIMEOUT')
                else:
                    require(now-self.last_receipt <= self.heartbeat_ticks, 'HEARTBEAT_TIMEOUT')
                    snapshot = self.profile.snapshot()
                    require(snapshot['fault'] is None, 'PROFILE_REVOKED')
            except Exception as error:
                reason = str(error) if type(error) is ValueError else 'ADAPTER_IO_OR_FORMAT_FAILURE'
                self.revoke(reason)

    def snapshot(self):
        self.poll()  # GET stays analysis-only; also detects a stalled background worker.
        with self.lock:
            value = self.profile.snapshot()
            if value['fault'] and self.status not in ('REVOKED', 'DISCONNECTED'):
                self.revoke('PROFILE_REVOKED')
            if self.status in ('REVOKED', 'DISCONNECTED'):
                value = self.profile.snapshot()
            waiting_pair = bool(self.queue or self.pairs or (self.market and self.market.partial)
                                or (self.timing and self.timing.partial))
            if self.status != 'LIVE_TAIL' or waiting_pair:
                value.update(market_stream='NOT_LIVE', analysis_status='BLOCKED')
                for component in value['components'].values():
                    component.update(status='BLOCKED', value=None)
            value.update(adapter_status=self.status, stream_mode=self.status,
                exporter_session_status='BOUND' if self.session and self.status not in ('REVOKED','DISCONNECTED') else self.status,
                exporter_session=self.session, canonical_sequence=self.sequence,
                timing_pair_status='WAITING' if waiting_pair else 'EXACT_PREFIX' if self.pair_sequence >= 0 else 'UNAVAILABLE',
                processing_age_status=value['processing_age']['status'], adapter_reason=self.reason,
                bootstrap_records=self.bootstrap_records, live_delivered_records=self.delivered_records,
                startup_cursor=None if not self.market else self.market.cursor,
                adapter_heartbeat=self.heartbeat, order_submit_reachable=False,
                transport_status='TRANSPORT_LIVE' if value['market_stream']=='LIVE' else 'NOT_LIVE')
            return value

    def close(self):
        self.revoke('ADAPTER_SHUTDOWN', disconnected=True)
