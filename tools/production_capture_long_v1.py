"""Operator-only long diagnostic capture. No runtime imports or time authority.

prepare --profile LONG_A|LONG_B|LONG_C creates a private directory. run observes
only that directory; the operator adds/removes the dedicated indicator manually.
acknowledge-remove confirms removal, never writer closure. Interrupted runs cannot
resume. replay checks retained bytes without renewing original receipt timestamps.
No live capture is performed by importing this module.
"""
import argparse
from contextlib import ExitStack, contextmanager
import ctypes
import hashlib
import os
from pathlib import Path
import queue
import threading
import time
from uuid import uuid4

from tools import production_capture_live_v1 as short
from tools import production_timing_long_v1 as production
from tools.production_capture_contract_v1 import Budget, Coordinator
from tools.production_capture_profiles_v1 import profile, PROFILES
from tools.native_receipt_ledger_v1 import (
    QpcGuard, canonical, digest, local, parse, require, write_new,
)

REFERENCES = short.REFERENCES
FLAGS = dict(runtime_admission=False, absolute_time_authority='UNKNOWN',
             data_freshness='NOT_ASSERTED', measurement_status='MEASURED_NOT_ATTESTED')
SOURCES = (*short.SOURCES, 'tools/production_capture_profiles_v1.py',
           'tools/production_timing_long_v1.py',
           'tools/production_capture_long_v1.py')


def pins():
    return {name: digest((short.ROOT / name).read_bytes()) for name in SOURCES}


def budget(p):
    return Budget(p.activation_timeout_seconds, p.minimum_duration_seconds,
                  p.acknowledgement_seconds, p.closure_seconds, p.final_clock_seconds)


def file_hash(path, limit, chunk=65536):
    h = hashlib.sha256()
    size = 0
    with local(path).open('rb') as f:
        identity = (os.fstat(f.fileno()).st_dev, os.fstat(f.fileno()).st_ino)
        while raw := f.read(chunk):
            size += len(raw)
            require(size <= limit, 'BYTE_CEILING')
            h.update(raw)
        require(f.tell() == os.fstat(f.fileno()).st_size, 'FILE_CHANGED')
    info = local(path).stat()
    require(identity == (info.st_dev, info.st_ino) and size == info.st_size, 'FILE_REPLACED')
    return identity, size, h.hexdigest()


def small(path, limit=65536):
    with local(path).open('rb') as f:
        raw = f.read(limit + 1)
    require(len(raw) <= limit, 'BYTE_CEILING')
    return raw


class DiskStream:
    """Bounded append-only reader; evidence payload is never retained in RAM.

    Live polls validate file identity/size and hash only newly observed bytes.
    Complete historical bytes are rehashed by verify() after writer closure or
    during replay. A split frame retains its original lower receipt bracket.
    """
    def __init__(self, path, profile_id, frequency, sample=short.qpc_pair,
                 byte_limit=None, record_limit=None):
        self.path, self.profile_id = local(path), profile_id
        self.p = profile(profile_id)
        self.limit = self.p.maximum_native_bytes if byte_limit is None else byte_limit
        self.record_limit = self.p.maximum_native_records if record_limit is None else record_limit
        self.guard, self.sample = QpcGuard(frequency), sample
        self.identity = None
        self.size = 0
        self.hasher = hashlib.sha256()
        self.index = []
        self.partial = b''
        self.partial_before = None
        self.failed = False

    @property
    def sha256(self):
        return self.hasher.hexdigest()

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        offset, size = self.index[i]
        with local(self.path).open('rb') as f:
            f.seek(offset)
            frame = f.read(size)
        require(len(frame) == size and frame.endswith(b'\n'), 'TRUNCATED_FRAME')
        return frame[:-1].removesuffix(b'\r')

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def _position_for_append(self, f):
        """Cheap live check: identity/bounds only; historical bytes are not reread."""
        info = os.fstat(f.fileno())
        ident = (info.st_dev, info.st_ino)
        require(info.st_ino and self.identity in (None, ident), 'FILE_REPLACED')
        require(self.size <= info.st_size <= self.limit, 'TRUNCATION_OR_BYTE_CEILING')
        f.seek(self.size)
        return ident, info.st_size

    def verify(self):
        """Full immutable verification, used only after closure/replay."""
        require(not self.failed and self.identity is not None, 'STREAM_FAILED')
        ident, size, sha = file_hash(
            self.path,
            self.limit,
            chunk=self.p.read_chunk_bytes,
        )
        require(
            ident == self.identity
            and size == self.size
            and sha == self.sha256,
            'PREFIX_MUTATION',
        )

    def poll(self):
        require(not self.failed, 'STREAM_FAILED')
        try:
            with local(self.path).open('rb', buffering=0) as f:
                ident, end = self._position_for_append(f)
                self.identity = ident
                while self.size < end:
                    before = self.sample(); self.guard.accept(before)
                    raw = f.read(min(self.p.read_chunk_bytes, end-self.size))
                    after = self.sample(); self.guard.accept(after)
                    require(raw, 'FILE_TRUNCATED')
                    start = self.size - len(self.partial)
                    self.size += len(raw); self.hasher.update(raw)
                    data = self.partial + raw
                    low = self.partial_before if self.partial_before is not None else before['qpc_before']
                    pos = 0
                    while True:
                        stop = data.find(b'\n', pos)
                        if stop < 0:
                            break
                        frame = data[pos:stop+1]
                        line = frame[:-1].removesuffix(b'\r')
                        require(line and b'\r' not in line and len(frame) <= self.p.maximum_frame_bytes,
                                'FRAME_CEILING')
                        require(len(self.index) < self.record_limit, 'RECORD_CEILING')
                        self.index.append((start+pos, len(frame)))
                        yield line, start+pos, len(frame), low, after['qpc_after']
                        pos = stop+1; low = before['qpc_before']
                    self.partial = data[pos:]
                    require(len(self.partial) <= self.p.maximum_frame_bytes, 'FRAME_CEILING')
                    self.partial_before = low if self.partial else None
                info = local(self.path).stat()
                require((info.st_dev, info.st_ino) == ident and info.st_size >= self.size, 'FILE_REPLACED')
        except BaseException:
            self.failed = True
            raise


class Journal:
    """Single-owner append-only durable JSONL with bounded streaming verification."""
    def __init__(self, path, profile_id, *, kind):
        self.path, self.p = local(path), profile(profile_id)
        require(kind in ('receipt', 'clock', 'windows'), 'JOURNAL_KIND')
        self.limit = self.p.maximum_clock_bytes if kind == 'clock' else self.p.maximum_receipt_bytes
        self.ceiling = self.p.maximum_clock_attempts if kind == 'clock' else self.p.maximum_receipt_records
        write_new(self.path, b'')
        self.identity = (self.path.stat().st_dev, self.path.stat().st_ino)
        self.size = self.count = 0
        self.hasher = hashlib.sha256()
        self.failed = False

    def append(self, row):
        require(not self.failed, 'JOURNAL_FAILED')
        try:
            raw = canonical(row) + b'\n'
            require(len(raw) <= self.p.maximum_frame_bytes and self.size+len(raw) <= self.limit, 'BYTE_CEILING')
            require(self.count < self.ceiling, 'RECORD_CEILING')
            with local(self.path).open('ab', buffering=0) as f:
                info = os.fstat(f.fileno())
                require((info.st_dev, info.st_ino) == self.identity and info.st_size == self.size, 'JOURNAL_CHANGED')
                require(f.write(raw) == len(raw), 'SHORT_WRITE')
                os.fsync(f.fileno())
            self.hasher.update(raw); self.size += len(raw); self.count += 1
        except BaseException:
            self.failed = True
            raise

    def quick_verify(self):
        """Live structural check without rereading the historical journal."""
        require(not self.failed, 'JOURNAL_FAILED')
        info = local(self.path).stat()
        require(
            (info.st_dev, info.st_ino) == self.identity
            and info.st_size == self.size,
            'JOURNAL_CHANGED',
        )

    def verify(self):
        """Full hash verification after capture/finalization."""
        require(not self.failed, 'JOURNAL_FAILED')
        require(
            file_hash(self.path, self.limit)
            == (self.identity, self.size, self.hasher.hexdigest()),
            'JOURNAL_TAMPERED',
        )

    def rows(self):
        self.verify()
        yield from read_journal(self.path, self.p.profile_id, self.limit, self.ceiling)
        self.verify()


def read_journal(path, profile_id, limit, ceiling):
    p = profile(profile_id)
    require(limit in (p.maximum_clock_bytes, p.maximum_receipt_bytes)
            and ceiling in (p.maximum_clock_attempts, p.maximum_receipt_records), 'PROFILE_LIMIT')
    count = size = 0
    with local(path).open('rb') as f:
        while raw := f.readline(p.maximum_frame_bytes+1):
            count += 1; size += len(raw)
            require(count <= ceiling and size <= limit and len(raw) <= p.maximum_frame_bytes
                    and raw.endswith(b'\n'), 'JOURNAL_CEILING_OR_TRUNCATION')
            row = parse(raw)
            require(canonical(row)+b'\n' == raw, 'JOURNAL_ENCODING')
            yield row


class Receipts:
    def __init__(self, path, run_id, frequency, profile_id):
        self.journal = Journal(path, profile_id, kind='receipt')
        self.run_id, self.frequency = run_id, frequency
        self.previous = None
        self.offset = 0

    def observe(self, raw, offset, size, before, after):
        row = parse(raw)
        require(type(row['sequence']) is int and row['sequence'] == self.journal.count, 'RECEIPT_CONFLICT')
        require(offset == self.offset and 0 <= before <= after, 'RECEIPT_OFFSET_OR_QPC')
        if self.previous:
            require(row['session'] == self.previous['native_session'], 'SESSION_CHANGED')
            require(before >= self.previous['receipt_qpc_before']
                    and after >= self.previous['receipt_qpc_after'], 'RECEIPT_REGRESSION')
        entry = dict(schema='arms.diagnostic-native-receipt.v1', run_id=self.run_id,
                     native_session=row['session'], canonical_sequence=row['sequence'], canonical_kind=row['kind'],
                     canonical_file_offset=offset, canonical_frame_bytes=size,
                     canonical_raw_sha256=digest(raw), receipt_qpc_before=before, receipt_qpc_after=after,
                     qpc_frequency=self.frequency, canonical_event_time=row['event_time'])
        self.journal.append(entry)
        self.previous = entry; self.offset += size
        return entry


@contextmanager
def exclusive(paths):
    """Deny write/delete sharing while allowing our bounded replay read handles."""
    require(os.name == 'nt', 'WINDOWS_REQUIRED')
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                       ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    create.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    with ExitStack() as stack:
        for path in paths:
            handle = create(str(local(path)), 0x80000000, 1, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                if ctypes.get_last_error() in (32, 33):
                    yield None
                    return
                raise OSError('EXCLUSIVE_READ_FAILED')
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except BaseException:
                kernel.CloseHandle(handle)
                raise
            stack.enter_context(os.fdopen(fd, 'rb'))
        yield True


class SealedCapture:
    def __init__(self, monitor, proof):
        self.profile_id, self.proof = monitor.p.profile_id, proof
        self.monitor = monitor
        # One complete hash at immutable closure establishes the sealed signature.
        self.signature = tuple(
            (str(p), *file_hash(p, monitor.p.maximum_native_bytes))
            for p in sorted(monitor.actual)
        )

    def quick_verify(self):
        """Cheap post-closure check; final verify() rehashes all bytes."""
        m = self.monitor
        m.inventory()
        expected = tuple(
            (path, identity, size)
            for path, identity, size, _sha in self.signature
        )
        current = []
        for path in sorted(m.actual):
            info = local(path).stat()
            current.append(
                (
                    str(path),
                    (info.st_dev, info.st_ino),
                    info.st_size,
                )
            )
        require(tuple(current) == expected, 'SEALED_FILES_CHANGED')

    def verify(self):
        """Full immutable byte/hash verification before COMPLETE/replay."""
        m = self.monitor
        m.inventory()
        require(
            self.signature
            == tuple(
                (str(p), *file_hash(p, m.p.maximum_native_bytes))
                for p in sorted(m.actual)
            ),
            'SEALED_FILES_CHANGED',
        )


class Monitor:
    def __init__(self, folder, manifest, sample=short.qpc_pair):
        self.folder, self.manifest, self.sample = folder, manifest, sample
        self.p = profile(manifest['profile']['profile_id'])
        self.frequency = manifest['qpc_frequency']
        self.receipts = Receipts(folder/'receipts/records.jsonl', manifest['run_id'], self.frequency, self.p.profile_id)
        self.streams = {}
        self.session = None
        self.closed = 0
        self.sealed = None
        self.actual = set()

    def inventory(self):
        market = local(self.folder/'market')
        actual = set()
        for path in market.rglob('*'):
            local(path)
            if path.is_dir():
                require(path == market/'timing', 'UNEXPECTED_NATIVE_DIRECTORY')
            else:
                actual.add(path)
                require(len(actual) <= self.p.maximum_native_files, 'NATIVE_FILE_CEILING')
        candidates = [p for p in actual if p.parent == market and p.suffix == '.jsonl'
                      and not p.name.endswith('.connection.jsonl')]
        require(len(candidates) <= 1, 'MULTIPLE_CANONICAL_SESSIONS')
        if not candidates:
            require(not actual and self.session is None, 'CANONICAL_DISAPPEARED')
            self.actual = actual
            return None
        path = candidates[0]
        from uuid import UUID
        session = path.stem
        require(str(UUID(session)) == session and self.session in (None, session), 'SESSION_CHANGED')
        self.session = session
        timing = market/'timing'/f'{session}.production-timing.jsonl'
        seal = Path(str(timing)+'.done.json')
        allowed = {path, market/f'{session}.connection.jsonl', timing, seal, Path(str(timing)+'.done.tmp')}
        require(actual <= allowed and set(self.streams) <= actual, 'NATIVE_INVENTORY_CHANGED')
        self.actual = actual
        return path, timing, seal

    def poll(self):
        paths = self.inventory()
        if paths is None:
            return None
        if self.sealed:
            self.sealed.quick_verify()
            self.receipts.journal.quick_verify()
            return self.sealed
        canonical_path, timing, seal = paths
        for path in sorted(self.actual):
            # The published seal is one bounded JSON document, not JSONL.
            # Never feed it through DiskStream/newline framing.
            if path == seal:
                require(path.stat().st_size <= 4096, 'SEAL_SIZE')
                continue
            if path.name.endswith('.tmp'):
                require(path.stat().st_size <= 4096, 'SEAL_SIZE')
                continue
            stream = self.streams.get(path)
            if stream is None:
                stream = DiskStream(
                    path,
                    self.p.profile_id,
                    self.frequency,
                    self.sample,
                )
                self.streams[path] = stream
            for raw, offset, size, low, high in stream.poll():
                if path == canonical_path:
                    r = self.receipts.observe(raw, offset, size, low, high)
                    require(r['native_session'] == self.session, 'SESSION_CHANGED')
                    if r['canonical_kind'] == 'CLOSED':
                        self.closed += 1
                elif path == timing:
                    row = parse(raw)
                    require(row['session'] == self.session and row['qpc_frequency'] == self.frequency
                            and row['pair_sequence'] == len(stream)-1, 'TIMING_DISCONTINUITY')
        # During live capture only check ownership/size. Full hash replay occurs
        # after native closure and again during final verification.
        self.receipts.journal.quick_verify()
        if seal in self.actual:
            require(Path(str(timing)+'.done.tmp') not in self.actual, 'SEAL_PUBLICATION_INCOMPLETE')
            with exclusive(paths) as closed:
                if not closed:
                    return None
                # Only newline-delimited native streams use DiskStream.
                for stream_path in (canonical_path, timing):
                    stream = self.streams.get(stream_path)
                    require(stream is not None, 'NATIVE_STREAM_MISSING')
                    stream.verify()
                    require(not stream.partial, 'INCOMPLETE_FRAME')

                # The seal is an immutable bounded JSON document.
                seal_raw = small(seal, 4096)
                _, seal_size, _ = file_hash(seal, 4096)
                require(seal_size == len(seal_raw), 'SEAL_CHANGED')

                windows = Journal(
                    self.folder/'final/emission-windows.jsonl',
                    self.p.profile_id,
                    kind='windows',
                )
                proof = production.adjudicate(
                    self.streams[canonical_path],
                    self.streams[timing],
                    seal_raw,
                    profile_id=self.p.profile_id,
                    window_sink=windows,
                )
                windows.verify()
                proof['emission_windows_artifact'] = dict(path='final/emission-windows.jsonl',
                    sha256=windows.hasher.hexdigest(), records=windows.count, bytes=windows.size)
                self.sealed = SealedCapture(self, proof)
                replay_receipts(self.receipts.journal.path, self.streams[canonical_path], self.streams[timing],
                                self.manifest['run_id'], self.frequency, self.p.profile_id)
            return self.sealed
        return None


def replay_receipts(path, native, timing, run_id, frequency, profile_id):
    p = profile(profile_id)
    native.verify(); timing.verify()
    previous = None
    pair_index = count = 0
    for r in read_journal(path, profile_id, p.maximum_receipt_bytes, p.maximum_receipt_records):
        from tools.native_receipt_ledger_v1 import FIELDS
        require(set(r) == FIELDS and r['schema'] == 'arms.diagnostic-native-receipt.v1', 'RECEIPT_SCHEMA')
        require(count < len(native), 'EXTRA_RECEIPTS')
        raw = native[count]; row = parse(raw); offset, size = native.index[count]
        require(r['run_id'] == run_id and r['qpc_frequency'] == frequency
                and r['canonical_sequence'] == count == row['sequence']
                and r['native_session'] == row['session'] and r['canonical_kind'] == row['kind']
                and r['canonical_event_time'] == row['event_time'] and r['canonical_raw_sha256'] == digest(raw)
                and r['canonical_file_offset'] == offset and r['canonical_frame_bytes'] == size, 'RECEIPT_BINDING')
        require(all(type(r[k]) is int for k in ('receipt_qpc_before','receipt_qpc_after','qpc_frequency',
                'canonical_sequence','canonical_file_offset','canonical_frame_bytes')), 'RECEIPT_INTEGER')
        require(0 <= r['receipt_qpc_before'] <= r['receipt_qpc_after'], 'RECEIPT_QPC')
        if previous:
            require(previous['native_session'] == r['native_session']
                    and previous['receipt_qpc_before'] <= r['receipt_qpc_before']
                    and previous['receipt_qpc_after'] <= r['receipt_qpc_after'], 'RECEIPT_REGRESSION')
        if row['kind'] in ('FORMING','CLOSED'):
            require(pair_index < len(timing), 'MISSING_PAIR')
            pair = parse(timing[pair_index]); pair_index += 1
            require(pair['canonical_sequence'] == count and pair['canonical_sha256'] == digest(raw)
                    and pair['session'] == row['session'] and pair['kind'] == row['kind']
                    and pair['emission']['qpc_after'] <= r['receipt_qpc_after'], 'RECEIPT_PAIR_BINDING')
        previous = r; count += 1
    require(count == len(native) and pair_index == len(timing), 'INCOMPLETE_REPLAY')
    native.verify(); timing.verify()
    return dict(records=count, pairs=pair_index, **FLAGS)


class ClockCollector(short.ClockCollector):
    """Reuse public-NTP probe acquisition, with bounded queue and disk journal."""
    def __init__(self, folder, manifest):
        super().__init__(folder, manifest['run_id'], manifest['qpc_frequency'])
        self.p = profile(manifest['profile']['profile_id'])
        self.items = queue.Queue(maxsize=self.p.maximum_queue_records)
        self.lock = threading.Lock()
        self.journal = Journal(folder/'clock/attempts.jsonl', self.p.profile_id, kind='clock')

    def work(self):
        try:
            while not self.stop.is_set():
                for reference in REFERENCES:
                    if self.stop.is_set():
                        return
                    require(self.journal.count < self.p.maximum_clock_attempts, 'CLOCK_ATTEMPT_CEILING')
                    raw, bridge = self.attempt(reference)
                    with self.lock:
                        row = dict(index=self.journal.count, raw_hex=raw.hex(), bridge=bridge)
                        self.journal.append(row)
                        self.items.put_nowait(row['index'])
                self.stop.wait(self.p.probe_cadence_seconds)
        except BaseException as error:
            self.error = type(error).__name__+':'+str(error)


def clocks(path, manifest):
    """Replay every attempt, including unsuccessful probes; no favorable selection."""
    p = profile(manifest['profile']['profile_id'])
    guard = QpcGuard(manifest['qpc_frequency'])
    for i, item in enumerate(read_journal(path, p.profile_id, p.maximum_clock_bytes, p.maximum_clock_attempts)):
        require(item['index'] == i, 'CLOCK_SEQUENCE')
        raw = bytes.fromhex(item['raw_hex']); b = item['bridge']; row = parse(raw)
        require(digest(raw) == b['measurement_sha256'] and row['epoch'] == manifest['run_id']
                and row['reference'] == REFERENCES[i % len(REFERENCES)], 'CLOCK_BINDING')
        guard.accept(b['before']); guard.accept(b['after'])
        if row['status'] == 'MEASURED_NOT_ATTESTED':
            decoded = short.clock.decode_reply(bytes.fromhex(row['packet_hex']),
                short.clock.encode_time(row['sent']['host_ns']), row['sent'], row['received'],
                row['reference'], manifest['run_id'])
            require(decoded == row, 'CLOCK_PACKET_REPLAY')
        else:
            require(row['status'] == 'PROBE_INVALID_OR_UNAVAILABLE', 'CLOCK_STATUS')
        yield raw, b


def clock_lists(path, manifest):
    # These are bounded by both fixed attempt and byte ceilings (maximum 32 MB
    # encoded on disk). Native six-hour evidence is never materialized here.
    valid = [(r,b) for r,b in clocks(path, manifest) if parse(r)['status'] == 'MEASURED_NOT_ATTESTED']
    return [x[0] for x in valid], [x[1] for x in valid]


def prepare(profile_id):
    p = profile(profile_id)
    initial = short.qpc_pair(); QpcGuard(initial['frequency']).accept(initial)
    run_id = str(uuid4())
    base = short.base_directory(); base.mkdir(parents=True, exist_ok=True)
    folder = base/run_id; folder.mkdir()
    for name in ('market','receipts','clock','final'):
        (folder/name).mkdir()
    manifest = dict(schema='arms.diagnostic-long-capture.v1', profile=p.manifest(),
        run_id=run_id, epoch=run_id, repo_head=short.head(), source_sha256=pins(),
        qpc_frequency=initial['frequency'], initial_qpc=initial,
        references=list(REFERENCES), reference_configuration=short.clock.REFERENCES,
        timescales=dict(canonical_candidate='UNSMEARED_UTC', public_ntp='DESCRIPTIVE_ONLY',
                        google='SMEARED_REFERENCE_DIAGNOSTIC_ONLY'),
        exporter_directory=str(folder/'market'), **FLAGS)
    short.write_json(folder/'run.json', manifest)
    short.replace_status(folder, dict(state='PREPARED', **FLAGS))
    return folder


def load_run(folder):
    folder = short.run_directory(folder)
    m = parse(small(folder/'run.json'))
    p = profile(m['profile']['profile_id'])
    require(m['schema'] == 'arms.diagnostic-long-capture.v1' and m['profile'] == p.manifest()
            and m['run_id'] == m['epoch'] == folder.name and m['repo_head'] == short.head()
            and m['source_sha256'] == pins() and m['references'] == list(REFERENCES)
            and m['reference_configuration'] == short.clock.REFERENCES
            and m['exporter_directory'] == str(folder/'market')
            and all(m[k] == v for k,v in FLAGS.items()), 'RUN_MANIFEST_CHANGED')
    QpcGuard(m['qpc_frequency']).accept(m['initial_qpc'])
    return folder, m


def acknowledge(folder):
    folder, m = load_run(folder)
    request = parse(small(folder/'remove-request.json'))
    state = parse(small(folder/'status.json'))
    require(state.get('state') == 'REMOVE_REQUESTED'
            and request.get('run_id') == m['run_id']
            and request.get('request_id') == state.get('request_id'),
            'NO_ACTIVE_REMOVE_REQUEST')
    q = short.qpc_pair(); QpcGuard(m['qpc_frequency'],request['request_qpc']).accept(q)
    short.write_json(folder/'remove-ack.json', dict(run_id=m['run_id'], request_id=request['request_id'],
                     native_session=request['native_session'], qpc=q, native_closure=False,
                     statement='I received and completed the manual remove request.'))


class Adapter(short.LiveAdapter):
    def __init__(self, folder, manifest, ready):
        super().__init__(folder, manifest, ready)
        p = profile(manifest['profile']['profile_id'])
        self.engine = Coordinator(run_id=manifest['run_id'], epoch=manifest['run_id'],
            frequency=ready['frequency'], ready_qpc=ready['qpc_after'], budget=budget(p), profile_id=p.profile_id)


def inventory(folder, p):
    result = {}
    for path in folder.rglob('*'):
        local(path)
        if path.is_file() and path != folder/'final/capture-manifest.json':
            require(len(result) < p.maximum_run_files, 'FILE_CEILING')
            _, size, sha = file_hash(path, max(p.maximum_native_bytes,p.maximum_clock_bytes,p.maximum_receipt_bytes))
            result[path.relative_to(folder).as_posix()] = dict(bytes=size, sha256=sha)
    return result


def run(folder):
    folder, m = load_run(folder)
    p = profile(m['profile']['profile_id'])
    require(not any((folder/'market').iterdir()), 'NATIVE_CAPTURE_ALREADY_STARTED')
    short.write_json(folder/'run-start.json', dict(pid=os.getpid(), qpc=short.qpc_pair(), **FLAGS))
    short.write_json(
        folder/'clock/windows-before.json',
        short.clock.windows_snapshot(),
    )
    # Descriptive host-clock state only. It grants no absolute-time authority.
    # Exclusive creation of run-start prevents interruption recovery or reuse.
    collector = ClockCollector(folder, m)
    monitor = Monitor(folder, m)
    adapter = Adapter(folder, m, short.qpc_pair()); c = adapter.engine
    ready = False
    completed_attempts = 0
    collector.thread.start()
    try:
        while c.state not in ('FAILED','COMPLETE'):
            while True:
                try:
                    index = collector.items.get_nowait()
                    require(index == completed_attempts, 'CLOCK_QUEUE_GAP')
                    completed_attempts += 1
                except queue.Empty:
                    break
            if not ready:
                require(not any((folder/'market').iterdir()), 'NATIVE_ACTIVATION_BEFORE_CLOCK_READY')
                ready = completed_attempts >= len(REFERENCES)
            sealed = monitor.poll() if ready else None
            adapter.step(short.qpc_pair(), session=monitor.session, closed=monitor.closed, sealed=sealed,
                         collector_alive=collector.thread.is_alive() and collector.error is None)
            if c.state == 'WAITING_FOR_ACTIVATION':
                short.replace_status(folder, dict(**c.snapshot(), native_activation_allowed=ready,
                                                exporter_directory=str(folder/'market')))
            if c.state == 'FINAL_CLOCK':
                # The worker may append concurrently. Only inspect the durable
                # prefix acknowledged by its queue, never a partial latest row.
                with collector_lock(collector):
                    raws, bridges = clock_lists(collector.journal.path, m)
                if all(any(parse(raw)['reference'] == ref and b['before']['qpc_before'] >= c.closure_qpc
                           for raw,b in zip(raws,bridges)) for ref in REFERENCES):
                    monitor.sealed.verify()
                    q = short.qpc_pair(); adapter.guard.accept(q)
                    c.finish(qpc=q['qpc_after'], epoch=c.epoch, frequency=q['frequency'],
                             measurements=raws, bridges=bridges, references=REFERENCES, unchanged_closed=True)
            # Do not full-hash the run while native/clock writers are active.
            # Live ceilings are enforced by the bounded stream/journal owners.
            # A complete artifact inventory is produced only after finalization.
            if c.state not in ('FAILED','COMPLETE'):
                time.sleep(1)
    except BaseException as error:
        c.fail('PROCESS_INTERRUPTED' if isinstance(error,(KeyboardInterrupt,SystemExit)) else str(error))
    finally:
        collector.stop.set(); collector.thread.join(6)
        if collector.thread.is_alive() or collector.error:
            c.fail('CLOCK_WORKER_FAILURE:'+str(collector.error))

    short.write_json(
        folder/'clock/windows-after.json',
        short.clock.windows_snapshot(),
    )

    try:
        load_run(folder)
        collector.journal.verify()
        for _ in clocks(collector.journal.path,m):
            pass
        monitor.receipts.journal.verify()
        if monitor.sealed:
            monitor.sealed.verify()
            short.write_json(folder/'final/production-adjudication.json',monitor.sealed.proof)
        short.write_json(folder/'final/coordinator.json',dict(snapshot=c.snapshot(),events=c.events))
        short.write_json(folder/'final/coverage.json',c.binding or dict(status='INCONCLUSIVE',reason=c.reason))
    except Exception as error:
        c.fail(str(error))
    result = dict(result='INCONCLUSIVE' if c.state == 'COMPLETE' or c.reason == 'INCOMPLETE_HISTORY' else 'FAIL',
                  structural_result='STRUCTURAL_PASS' if c.state == 'COMPLETE'
                  else 'INCONCLUSIVE' if c.reason == 'INCOMPLETE_HISTORY' else 'FAIL',
                  reason=c.reason, profile_id=p.profile_id, run_id=c.run_id, **FLAGS)
    short.replace_status(folder,result)
    short.write_json(folder/'final/capture-manifest.json', dict(**result, configuration=m, artifacts=inventory(folder,p)))
    return result


@contextmanager
def collector_lock(collector):
    with collector.lock:
        yield


def replay(folder):
    """Read-only final replay: validate recorded inventory and original receipts."""
    folder, m = load_run(folder); p = profile(m['profile']['profile_id'])
    final = parse(small(folder/'final/capture-manifest.json'))
    require(
        final['configuration'] == m
        and final['artifacts'] == inventory(folder,p),
        'FINAL_INVENTORY_CHANGED',
    )
    require(
        'clock/windows-before.json' in final['artifacts']
        and 'clock/windows-after.json' in final['artifacts'],
        'WINDOWS_TIME_EVIDENCE_MISSING',
    )
    require(
        final.get('profile_id') == p.profile_id
        and final.get('run_id') == m['run_id']
        and final.get('result') == 'INCONCLUSIVE'
        and final.get('structural_result') == 'STRUCTURAL_PASS'
        and final.get('reason') is None
        and all(final.get(k) == v for k, v in FLAGS.items()),
        'FINAL_PROFILE_COMPLETION',
    )

    coordinator = parse(small(folder/'final/coordinator.json'))
    snapshot = coordinator.get('snapshot', {})
    require(
        snapshot.get('state') == 'COMPLETE'
        and snapshot.get('reason') is None
        and snapshot.get('run_id') == m['run_id']
        and snapshot.get('runtime_admission') is False
        and snapshot.get('pending_closure') is False
        and snapshot.get('collector_must_continue') is False,
        'COORDINATOR_NOT_COMPLETE',
    )

    market = folder/'market'
    paths = [x for x in market.glob('*.jsonl') if not x.name.endswith('.connection.jsonl')]
    require(len(paths) == 1, 'NATIVE_INVENTORY')
    native_path = paths[0]; timing_path = market/'timing'/f'{native_path.stem}.production-timing.jsonl'
    # Replay indexing uses a synthetic bracket solely to read bytes. It never
    # writes or replaces the original receipt timestamps used below.
    q = dict(frequency=m['qpc_frequency'],qpc_before=0,qpc_after=0,host_unix_ns=0)
    streams = [DiskStream(path,p.profile_id,m['qpc_frequency'],lambda:q) for path in (native_path,timing_path)]
    for stream in streams:
        for _ in stream.poll():
            pass
        require(not stream.partial, 'INCOMPLETE_FRAME')
    class WindowVerifier:
        def __init__(self):
            self.rows = iter(read_journal(folder/'final/emission-windows.jsonl',p.profile_id,
                                         p.maximum_receipt_bytes,p.maximum_receipt_records))
        def append(self,row):
            require(next(self.rows,None) == row, 'WINDOW_REPLAY')
    sink = WindowVerifier()
    proof = production.adjudicate(*streams,small(Path(str(timing_path)+'.done.json'),4096),
                                 profile_id=p.profile_id,window_sink=sink)
    require(
        proof['status'] == 'PASS'
        and proof.get('closed', 0) >= p.minimum_closed
        and next(sink.rows, None) is None,
        'PRODUCTION_REPLAY',
    )
    receipts = replay_receipts(
        folder/'receipts/records.jsonl',
        *streams,
        m['run_id'],
        m['qpc_frequency'],
        p.profile_id,
    )
    for _ in clocks(folder/'clock/attempts.jsonl',m):
        pass
    require(final['artifacts'] == inventory(folder,p), 'FINAL_INVENTORY_CHANGED')
    return dict(profile_id=p.profile_id, production=proof, receipts=receipts, **FLAGS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command',required=True)
    subs.add_parser('prepare').add_argument('--profile',choices=tuple(PROFILES),required=True)
    for name in ('run','replay','status','acknowledge-remove'):
        subs.add_parser(name).add_argument('--run-directory',required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare(args.profile))
    elif args.command == 'run':
        print(canonical(run(args.run_directory)).decode())
    elif args.command == 'replay':
        print(canonical(replay(args.run_directory)).decode())
    elif args.command == 'acknowledge-remove':
        acknowledge(args.run_directory)
    else:
        folder,_ = load_run(args.run_directory)
        print(small(folder/'status.json').decode())


if __name__ == '__main__':
    main()
