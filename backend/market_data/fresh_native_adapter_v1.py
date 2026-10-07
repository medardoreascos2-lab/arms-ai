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
from backend.market_data.certified_bootstrap_v1 import CertifiedBootstrap
from backend.market_data.exporter_identity_v1 import verify_exporter_source
from tools.native_timing_witness_v1 import IDENTITY, check_pair, ticks, qpc_pair
from tools.production_timing_v1 import PAIR_FIELDS, SEAL_FIELDS, parse

MAX_FILE = 32 * 1024 * 1024
MAX_L1_FILE = 256 * 1024 * 1024
CHUNK = 65536
MAX_LINE = 16384
MAX_QUEUE = 1024

PREACTIVATION_HELLO_PAYLOAD = {
    'provider': 'Provider31',
    'contract': 'NQ DEC26',
    'expiry': '2026-12-01',
    'instrument': 'NQ',
    'tick_size': .25,
    'point_value': 20,
    'timeframe': '1m',
    'trading_hours_template': 'CME US Index Futures ETH',
    'source_timezone': 'UTC',
    'bar_label': 'CLOSE',
    'realtime': True,
    'read_only': True,
}


def _exact_prefix_digest(handle, size):
    """Hash exactly *size* bytes even when an unbuffered read is short."""
    require(type(size) is int and size >= 0, 'PREFIX_SIZE')
    digest = sha256()
    remaining = size
    while remaining:
        block = handle.read(min(CHUNK, remaining))
        require(bool(block), 'PREFIX_SHORT_READ')
        digest.update(block)
        remaining -= len(block)
    return digest.digest()


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
    def __init__(
        self,
        path,
        *,
        startup_cursor=None,
        max_file=None,
    ):
        self.max_file = MAX_FILE if max_file is None else max_file
        require(type(self.max_file) is int and 0 < self.max_file <= MAX_L1_FILE, 'FILE_LIMIT_CONFIG')
        self.path = local_path(path)
        self.handle = self._open_read(self.path)
        try:
            info = os.fstat(self.handle.fileno())
            self.identity = (info.st_dev, info.st_ino)
            require(info.st_ino and stat.S_ISREG(info.st_mode), 'FILE_IDENTITY_UNAVAILABLE')
            require(info.st_size <= self.max_file, 'FILE_LIMIT')
            require(
                startup_cursor is None
                or (
                    type(startup_cursor) is int
                    and 0 <= startup_cursor <= info.st_size
                ),
                'STARTUP_CURSOR_INVALID',
            )
        except Exception:
            self.handle.close()
            raise
        self.cursor = (
            info.st_size
            if startup_cursor is None
            else startup_cursor
        )
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
        require(self.offset <= info.st_size <= self.max_file, 'FILE_TRUNCATED_OR_LIMIT')
        # Verify the consumed prefix too: same-inode overwrite must not go unnoticed.
        self.handle.seek(0)
        require(_exact_prefix_digest(self.handle, self.offset) == self.digest.digest(), 'PREFIX_CHANGED')
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
                 startup_seconds=900, health_gated=True, bootstrap=None,
                 live_handoff=False):
        self.directory = local_path(directory)
        require(self.directory.is_dir(), 'DIRECTORY_REQUIRED')
        source = local_path(installed_exporter)
        self.exporter_identity = verify_exporter_source(source.read_bytes())
        require(all(type(v) in (int, float) and isfinite(v) and v > 0 for v in
                    (heartbeat_seconds, processing_seconds, pair_wait_seconds, startup_seconds)), 'AGE_BUDGET')
        # These are local observation cutoffs, not revised absolute timestamp tolerances.
        require(heartbeat_seconds <= 15 and processing_seconds <= 90 and pair_wait_seconds <= 5
                and startup_seconds <= 900, 'BUDGET_WIDENING')
        require(
            type(live_handoff) is bool,
            'LIVE_HANDOFF_FLAG',
        )
        self.clock = qpc_clock
        self.epoch, self.frequency, self.start = self.clock()
        require(isinstance(self.epoch, str) and bool(self.epoch) and type(self.frequency) is int
                and self.frequency > 0 and type(self.start) is int and self.start >= 0, 'QPC_CONTEXT')
        self.last_now = self.start
        self.health_gated = health_gated
        self.activation_start = None if health_gated else self.start
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
        self.live_handoff_enabled = live_handoff
        self.live_handoff_records = deque()
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
        self.preactivation_root_empty = not any(
            self.directory.iterdir()
        )
        self.preactivation_session = None
        self.preactivation_lineage_root = None
        self.preactivation_lineage_sessions = ()
        self.preactivation_transition_pending = False
        self.preactivation_identities = {}
        self.timing_identity = None
        self.bootstrap = bootstrap
        self.bootstrap_replacement_count = 0
        self.profile = self._new_profile(str(uuid4()))

    def _directory_identity(self):
        info = local_path(self.directory).stat()
        return info.st_dev, info.st_ino

    @staticmethod
    def _preactivation_session_from_name(name, suffix, reason):
        require(name.endswith(suffix), reason)
        value = name[:-len(suffix)]
        try:
            valid = str(UUID(value)) == value
        except (ValueError, TypeError, AttributeError):
            valid = False
        require(valid, reason)
        return value

    def _preactivation_identity_key(self, path):
        return str(local_path(path).relative_to(self.directory)).replace('\\', '/')

    def _pin_preactivation_path(self, path, present, reason, *, directory=False):
        value = local_path(path)
        info = value.stat()
        require(info.st_ino, reason)
        if directory:
            require(value.is_dir(), reason)
        else:
            require(value.is_file() and info.st_size <= MAX_FILE, reason)
        key = self._preactivation_identity_key(value)
        identity = (info.st_dev, info.st_ino)
        prior = self.preactivation_identities.get(key)
        require(prior is None or prior == identity, reason)
        if prior is None:
            self.preactivation_identities[key] = identity
        present.add(key)

    @staticmethod
    def _validate_preactivation_hello(row, session, reason):
        require(
            set(row) == set('schema session sequence event_time kind payload'.split())
            and row['schema'] == 'arms.nt.market.v1'
            and row['session'] == session
            and type(row['sequence']) is int
            and row['sequence'] == 0
            and row['kind'] == 'HELLO'
            and row['payload'] == PREACTIVATION_HELLO_PAYLOAD,
            reason,
        )
        ticks(row['event_time'])
        return row

    def _read_preactivation_hello(self, path, session, reason):
        value = local_path(path)
        require(value.stat().st_size <= MAX_FILE, reason)
        with value.open('rb') as handle:
            raw = handle.readline(MAX_LINE + 1)
        require(len(raw) <= MAX_LINE, reason)
        if not raw.endswith(b'\n'):
            return None
        return self._validate_preactivation_hello(
            parse(raw[:-1] if not raw.endswith(b'\r\n') else raw[:-2]),
            session,
            reason,
        )

    def _validate_closed_predecessor(
        self,
        session,
        canonical,
        timing,
        seals,
        reason,
    ):
        raw = local_path(canonical).read_bytes()
        require(0 < len(raw) <= MAX_FILE and raw.endswith(b'\n'), reason)
        lines = raw.splitlines()
        require(len(lines) >= 2, reason)
        rows = [parse(line) for line in lines]
        for sequence, row in enumerate(rows):
            require(
                set(row) == set('schema session sequence event_time kind payload'.split())
                and row['schema'] == 'arms.nt.market.v1'
                and row['session'] == session
                and type(row['sequence']) is int
                and row['sequence'] == sequence,
                reason,
            )
            ticks(row['event_time'])
            if sequence == 0:
                self._validate_preactivation_hello(row, session, reason)
            elif sequence == len(rows) - 1:
                require(
                    row['kind'] == 'DISCONNECTED'
                    and row['payload'] == {
                        'connected': False,
                        'reason': 'TERMINATED',
                        'error_code': 'NONE',
                    },
                    reason,
                )
            else:
                require(row['kind'] in ('HEARTBEAT', 'CLOSED', 'FORMING'), reason)

        require(session in timing and session in seals, reason)
        sidecar_raw = local_path(timing[session]).read_bytes()
        require(len(sidecar_raw) <= MAX_FILE, reason)
        if sidecar_raw:
            require(sidecar_raw.endswith(b'\n'), reason)
            timing_records = len(sidecar_raw.splitlines())
        else:
            timing_records = 0

        seal_raw = local_path(seals[session]).read_bytes()
        require(0 < len(seal_raw) <= 4096, reason)
        seal = parse(seal_raw)
        require(
            set(seal) == SEAL_FIELDS
            and seal['schema'] == 'arms.nt.production-timing.seal.v1'
            and seal['session'] == session
            and all(type(seal[key]) is int for key in (
                'records', 'bytes', 'canonical_records',
            ))
            and seal['records'] == timing_records
            and seal['bytes'] == len(sidecar_raw)
            and seal['sha256'] == sha256(sidecar_raw).hexdigest()
            and seal['canonical_records'] == len(rows)
            and seal['canonical_writer_closed'] is True
            and seal['timing_writer_closed'] is True
            and seal['complete'] is True,
            reason,
        )
        return rows[-1]

    def validate_preactivation_buffer(
        self,
        reason="INPUT_BEFORE_ACTIVATION_ALLOWANCE",
    ):
        """Validate one logical preactivation lineage without consuming it."""
        with self.lock:
            require(type(reason) is str and bool(reason), "PREACTIVATION_BUFFER_REASON")
            require(self._directory_identity() == self.root_identity, reason)

            entries = tuple(self.directory.iterdir())
            if entries:
                require(self.preactivation_root_empty, reason)

            canonical = {}
            connections = {}
            timing = {}
            seals = {}
            present = set()

            for raw_entry in entries:
                if raw_entry.name == 'timing':
                    folder = local_path(raw_entry)
                    self._pin_preactivation_path(
                        folder,
                        present,
                        reason,
                        directory=True,
                    )
                    for raw_sidecar in folder.iterdir():
                        sidecar = local_path(raw_sidecar)
                        require(sidecar.is_file(), reason)
                        if sidecar.name.endswith('.production-timing.jsonl.done.json'):
                            session = self._preactivation_session_from_name(
                                sidecar.name,
                                '.production-timing.jsonl.done.json',
                                reason,
                            )
                            require(session not in seals, reason)
                            seals[session] = sidecar
                        elif sidecar.name.endswith('.production-timing.jsonl'):
                            session = self._preactivation_session_from_name(
                                sidecar.name,
                                '.production-timing.jsonl',
                                reason,
                            )
                            require(session not in timing, reason)
                            timing[session] = sidecar
                        else:
                            raise ValueError(reason)
                        self._pin_preactivation_path(sidecar, present, reason)
                    continue

                entry = local_path(raw_entry)
                require(entry.is_file(), reason)
                if entry.name.endswith('.connection.jsonl'):
                    session = self._preactivation_session_from_name(
                        entry.name,
                        '.connection.jsonl',
                        reason,
                    )
                    require(session not in connections, reason)
                    connections[session] = entry
                elif entry.name.endswith('.jsonl'):
                    session = self._preactivation_session_from_name(
                        entry.name,
                        '.jsonl',
                        reason,
                    )
                    require(session not in canonical, reason)
                    canonical[session] = entry
                else:
                    raise ValueError(reason)
                self._pin_preactivation_path(entry, present, reason)

            for key in self.preactivation_identities:
                require(key in present, reason)

            sessions = set(canonical)
            sidecar_sessions = (
                set(connections)
                | set(timing)
                | set(seals)
            )

            if not sessions:
                require(self.preactivation_lineage_root is None, reason)
                require(
                    len(sidecar_sessions) <= 1
                    and set(seals).issubset(set(timing)),
                    reason,
                )
                # The native exporter may publish diagnostics before its
                # canonical stream.  Their identities remain pinned, but
                # only the canonical sequence-zero HELLO can bind a session.
                return None

            require(
                set(connections).issubset(sessions)
                and set(timing).issubset(sessions)
                and set(seals).issubset(sessions)
                and len(sessions) <= 2,
                reason,
            )

            if self.preactivation_lineage_root is None:
                require(len(sessions) == 1, reason)
                root = next(iter(sessions))
                hello = self._read_preactivation_hello(canonical[root], root, reason)
                if hello is None:
                    return None
                self.preactivation_lineage_root = root
                self.preactivation_lineage_sessions = (root,)
                self.preactivation_session = root
            else:
                root = self.preactivation_lineage_root
                require(root in sessions, reason)

            if len(sessions) == 1:
                require(
                    sessions == {root}
                    and self.preactivation_lineage_sessions == (root,),
                    reason,
                )
                self.preactivation_transition_pending = False
                return root

            replacement = next(iter(sessions - {root}))
            terminal = self._validate_closed_predecessor(
                root,
                canonical[root],
                timing,
                seals,
                reason,
            )
            hello = self._read_preactivation_hello(
                canonical[replacement],
                replacement,
                reason,
            )

            if hello is None:
                require(
                    self.preactivation_lineage_sessions == (root,)
                    and self.activation_start is None
                    and self.bootstrap_replacement_count == 0,
                    reason,
                )
                self.preactivation_transition_pending = True
                return root

            require(ticks(terminal['event_time']) < ticks(hello['event_time']), reason)

            lineage = (root, replacement)
            if self.preactivation_lineage_sessions == (root,):
                require(
                    self.activation_start is None
                    and self.bootstrap_replacement_count == 0,
                    reason,
                )
                self.preactivation_lineage_sessions = lineage
                self.preactivation_session = replacement
            else:
                require(self.preactivation_lineage_sessions == lineage, reason)
                require(self.preactivation_session == replacement, reason)

            self.preactivation_transition_pending = False
            return replacement

    def _preactivation_startup_cursor(
        self,
        session,
        key,
        path,
    ):
        """Return zero only for the one session born after this fresh runtime."""
        if not (
            self.health_gated
            and self.preactivation_root_empty
            and self.preactivation_session
            == session
        ):
            return None

        value = local_path(
            path
        )

        info = value.stat()

        require(
            info.st_ino,
            'PREACTIVATION_BUFFER_IDENTITY',
        )

        prior = (
            self.preactivation_identities
            .get(
                self._preactivation_identity_key(
                    value
                )
            )
        )

        # If the file existed before activation, its exact file
        # identity must still be the one that was quarantined.
        if prior is not None:
            require(
                prior
                == (
                    info.st_dev,
                    info.st_ino,
                ),
                'PREACTIVATION_BUFFER_IDENTITY',
            )

        # Zero does not mean trusted history. It only means:
        # parse the runtime-local prefix and let QPC/provenance/
        # overlap gates decide what can become LIVE_TAIL.
        return 0

    def replace_waiting_bootstrap(self, bootstrap):
        """Replace bootstrap once before activation; never after any live input."""
        with self.lock:
            require(
                type(bootstrap) is CertifiedBootstrap,
                'CERTIFIED_BOOTSTRAP_REQUIRED',
            )
            require(
                self.health_gated
                and self.activation_start is None
                and self.status == 'WAITING'
                and self.session is None
                and self.market is None
                and self.timing is None
                and self.bootstrap_replacement_count == 0,
                'BOOTSTRAP_REPLACEMENT_STATE',
            )
            self.validate_preactivation_buffer(
                'BOOTSTRAP_REPLACEMENT_NOT_FRESH',
            )

            require(
                not self.preactivation_transition_pending,
                'BOOTSTRAP_REPLACEMENT_NOT_FRESH',
            )

            require(
                self._directory_identity()
                == self.root_identity
                and not self.queue
                and not self.pairs
                and self.sequence == -1
                and self.pair_sequence == -1
                and self.hello is None
                and self.last_pair is None
                and self.last_receipt is None
                and self.bootstrap_records == 0
                and self.delivered_records == 0,
                'BOOTSTRAP_REPLACEMENT_NOT_FRESH',
            )

            self.bootstrap = bootstrap
            self.profile = self._new_profile(
                str(uuid4())
            )
            self.bootstrap_replacement_count = 1

    def arm_live_handoff(self):
        """One-shot opt-in before activation; never a PAPER/execution control."""
        with self.lock:
            require(
                not self.live_handoff_enabled
                and self.health_gated
                and self.activation_start is None
                and self.status == 'WAITING'
                and self.reason is None
                and self.session is None
                and self.market is None
                and self.timing is None
                and not self.queue
                and not self.pairs
                and self.sequence == -1
                and self.pair_sequence == -1
                and self.hello is None
                and self.last_pair is None
                and self.last_receipt is None
                and self.bootstrap_records == 0
                and self.delivered_records == 0
                and not self.live_handoff_records,
                'LIVE_HANDOFF_ARM_REENTRY_OR_INVALID_STATE',
            )

            require(
                type(self.bootstrap)
                is CertifiedBootstrap
                and bool(self.bootstrap.bars)
                and self.profile.bootstrap
                is self.bootstrap,
                'LIVE_HANDOFF_CERTIFIED_BOOTSTRAP_REQUIRED',
            )

            # A fresh runtime-local exporter may already be
            # quarantined here by the Single-Apply startup.
            # Validate/pin it but never consume it.
            self.validate_preactivation_buffer(
                'LIVE_HANDOFF_ARM_INPUT_NOT_FRESH',
            )

            require(
                not self.preactivation_transition_pending,
                'LIVE_HANDOFF_ARM_INPUT_NOT_FRESH',
            )

            require(
                self._directory_identity()
                == self.root_identity,
                'LIVE_HANDOFF_ARM_INPUT_NOT_FRESH',
            )

            self.live_handoff_enabled = True

    def arm_activation(self):
        """In-process coordinator only; no HTTP/file-based arming or reset."""
        with self.lock:
            require(self.health_gated and self.activation_start is None and self.status == 'WAITING'
                    and self.session is None, 'ACTIVATION_REENTRY_OR_INVALID_STATE')
            self.validate_preactivation_buffer(
                'ACTIVATION_INPUT_NOT_FRESH',
            )
            require(
                not self.preactivation_transition_pending,
                'ACTIVATION_INPUT_NOT_FRESH',
            )
            require(
                self._directory_identity()
                == self.root_identity,
                'ACTIVATION_INPUT_NOT_FRESH',
            )
            self.activation_start = self.sample()[2]

    def sample(self):
        epoch, frequency, now = self.clock()
        require(epoch == self.epoch and type(frequency) is int and frequency == self.frequency
                and type(now) is int and now >= self.last_now, 'QPC_EPOCH_OR_REGRESSION')
        self.last_now = now
        return epoch, frequency, now

    def _new_profile(self, session, *, warm=True):
        return MarketAnalysisTimeProfileV1(session=session, epoch=self.epoch, frequency=self.frequency,
            reader_start_qpc=self.start, qpc_clock=self.sample, exporter_sha256=EXPORTER_SHA256,
            bootstrap=self.bootstrap if warm else None, **self.options)

    def revoke(self, reason='ADAPTER_STOPPED', *, disconnected=False):
        with self.lock:
            if self.status not in ('REVOKED', 'DISCONNECTED'):
                self.reason = reason
                self.status = 'DISCONNECTED' if disconnected else 'REVOKED'
                self.profile.revoke(reason)
                self.live_handoff_records.clear()
                for tail in (self.market, self.timing):
                    if tail is not None:
                        tail.close()

    def diagnostics(self):
        """Read latched fault evidence without polling or sampling QPC."""
        with self.lock:
            profile = self.profile.diagnostics()
            return dict(adapter_reason=self.reason,
                profile_fault=profile['fault'],
                profile_fault_first_qpc=profile['fault_first_qpc'],
                profile_fault_last_qpc=profile['fault_last_qpc'],
                profile_last_receipt_qpc=profile['last_receipt_qpc'],
                profile_last_emission_qpc=profile['last_emission_qpc'],
                profile_heartbeat_budget_qpc=profile['heartbeat_budget_qpc'],
                profile_processing_budget_qpc=profile['processing_budget_qpc'])

    def _discover(self, now):
        require(self._directory_identity() == self.root_identity, 'DIRECTORY_REPLACED')
        if self.activation_start is None:
            self.validate_preactivation_buffer(
                'INPUT_BEFORE_ACTIVATION_ALLOWANCE',
            )
            return

        lineage_session = None
        if (
            self.health_gated
            and self.preactivation_root_empty
            and self.preactivation_lineage_root is not None
        ):
            lineage_session = self.validate_preactivation_buffer(
                'SESSION_ROTATION',
            )
            require(
                lineage_session is not None
                and lineage_session == self.preactivation_session
                and not self.preactivation_transition_pending,
                'SESSION_ROTATION',
            )

        candidates = sorted(
            p for p in self.directory.glob('*.jsonl')
            if not p.name.endswith('.connection.jsonl')
        )

        if lineage_session is not None:
            require(
                {path.stem for path in candidates}
                == set(self.preactivation_lineage_sessions),
                'SESSION_ROTATION',
            )
            path = self.directory / (lineage_session + '.jsonl')
            require(path in candidates, 'SESSION_ROTATION')
        else:
            require(len(candidates) <= 1, 'SESSION_ROTATION')
            if not candidates:
                require(self.market is None, 'MARKET_FILE_REMOVED')
                require(now-self.activation_start <= self.startup_ticks, 'ACTIVATION_TIMEOUT')
                return
            path = candidates[0]

        session = path.stem
        require(str(UUID(session)) == session, 'SESSION_FILENAME')
        require(self.session is None or session == self.session, 'SESSION_ROTATION')
        if self.market is None:
            self.market = _Tail(
                path,
                startup_cursor=
                    self._preactivation_startup_cursor(
                        session,
                        "canonical",
                        path,
                    ),
            )
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
            if lineage_session is not None:
                require(
                    {self._preactivation_session_from_name(
                        p.name,
                        '.production-timing.jsonl',
                        'SIDECAR_SESSION_ROTATION',
                    ) for p in files}
                    .issubset(set(self.preactivation_lineage_sessions)),
                    'SIDECAR_SESSION_ROTATION',
                )
            else:
                require(all(p.name == session+'.production-timing.jsonl' for p in files), 'SIDECAR_SESSION_ROTATION')
            sidecar = folder/(session+'.production-timing.jsonl')
            if sidecar.exists() and self.timing is None:
                self.timing = _Tail(
                    sidecar,
                    startup_cursor=
                        self._preactivation_startup_cursor(
                            session,
                            "timing",
                            sidecar,
                        ),
                )
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
            probe = self._new_profile(self.session, warm=False)
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

                    quarantined_replay = (
                        self.status == 'BOOTSTRAP'
                        and self.health_gated
                        and self.preactivation_root_empty
                        and self.preactivation_session
                        == self.session
                        and self.market.cursor == 0
                    )

                    stale_quarantined_pair = (
                        bool(pair)
                        and quarantined_replay
                        and (
                            now
                            - pair['emission'][
                                'qpc_before'
                            ]
                            > int(
                                self.options[
                                    'maximum_processing_seconds'
                                ]
                                * self.frequency
                            )
                        )
                    )

                    historical = (
                        offset
                        < self.market.cursor
                        or (
                            pair
                            and pair[
                                'callback'
                            ][
                                'qpc_before'
                            ]
                            < self.start
                        )
                        or stale_quarantined_pair
                    )

                    if self.status == 'BOOTSTRAP' and pair and not historical and row['kind'] == 'FORMING':
                        # Boundary-local warmup: producer may already emit CLOSED at every boundary.
                        self.profile.establish_tail_baseline(self.hello, canonical_sequence=self.sequence,
                                                             pair_sequence=self.pair_sequence)
                        self.status = 'LIVE_TAIL'
                    if self.status == 'LIVE_TAIL':
                        require(not historical, 'OLD_ROW_AFTER_BASELINE')
                        delivery = self.profile.accept(
                            raw,
                            paired,
                            receipt_qpc=receipt,
                        )
                        if (
                            delivery is not None
                            and self.live_handoff_enabled
                        ):
                            require(
                                len(
                                    self.live_handoff_records
                                )
                                < MAX_QUEUE,
                                'LIVE_HANDOFF_QUEUE_LIMIT',
                            )
                            self.live_handoff_records.append(
                                delivery
                            )
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

    def drain_live_closed_records(self):
        """Drain already-certified LIVE CLOSED records.

        This is an explicit data handoff only.  It never imports,
        constructs or calls an account/execution service.
        """
        with self.lock:
            require(
                self.live_handoff_enabled,
                'LIVE_HANDOFF_DISABLED',
            )

            if (
                self.status != 'LIVE_TAIL'
                or self.reason is not None
            ):
                self.live_handoff_records.clear()
                return ()

            result = tuple(
                dict(value)
                for value
                in self.live_handoff_records
            )

            self.live_handoff_records.clear()

            return result

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
                    if component['status'] != 'CERTIFIED_BOOTSTRAP_ONLY':
                        component.update(status='BLOCKED', value=None)
            value.update(adapter_status=self.status, stream_mode=self.status,
                exporter_session_status='BOUND' if self.session and self.status not in ('REVOKED','DISCONNECTED') else self.status,
                exporter_session=self.session, canonical_sequence=self.sequence,
                timing_pair_status='WAITING' if waiting_pair else 'EXACT_PREFIX' if self.pair_sequence >= 0 else 'UNAVAILABLE',
                processing_age_status=value['processing_age']['status'], adapter_reason=self.reason,
                bootstrap_records=self.bootstrap_records, live_delivered_records=self.delivered_records,
                startup_cursor=None if not self.market else self.market.cursor,
                adapter_heartbeat=self.heartbeat, order_submit_reachable=False,
                activation_allowance_started=self.activation_start is not None,
                transport_status='TRANSPORT_LIVE' if value['market_stream']=='LIVE' else 'NOT_LIVE')
            value.update(self.diagnostics(),
                profile_receipt_age_seconds=value['receipt_age_seconds'],
                profile_emission_age_seconds=value['emission_age_seconds'])
            return value

    def close(self):
        self.revoke('ADAPTER_SHUTDOWN', disconnected=True)
