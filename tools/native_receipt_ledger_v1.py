"""Diagnostic receipt evidence: exact bytes observed inside a Windows QPC bracket.

Not exchange event time, UTC accuracy, freshness, or runtime admission. No recovery
of a live reader is permitted. Replay validates evidence; it never renews receipts.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
from uuid import UUID

from tools.native_timing_witness_v1 import parse, qpc_pair


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def local(path):
    path = Path(path).absolute()
    require(not str(path).startswith(('\\\\', '//')), 'LOCAL_PATH_REQUIRED')
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 1024,
                    'REPARSE_PATH')
    return path


def write_new(path, raw):
    path = local(path)
    with path.open('xb') as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


class QpcGuard:
    def __init__(self, frequency, last=0):
        require(type(frequency) is int and frequency > 0, 'QPC_FREQUENCY')
        self.frequency, self.last = frequency, last

    def accept(self, pair):
        require(all(type(pair[k]) is int for k in ('frequency', 'qpc_before', 'qpc_after', 'host_unix_ns')),
                'QPC_FIELDS')
        require(pair['frequency'] == self.frequency, 'QPC_FREQUENCY_CHANGED')
        require(self.last <= pair['qpc_before'] <= pair['qpc_after'], 'QPC_REGRESSION')
        self.last = pair['qpc_after']


class StableFile:
    """Bounded prefix-verified reads. QPC brackets surround each actual file read.

    A partial line keeps the earliest bracket of its bytes. Replacement, shrinking,
    and same-inode prefix edits fail. Hashes exclude CRLF, matching native sidecars;
    offsets and frame sizes include the exact on-disk line terminator.
    """
    def __init__(self, path, frequency, sample=qpc_pair, limit=2_000_000):
        self.path, self.sample, self.limit = local(path), sample, limit
        self.guard = QpcGuard(frequency)
        self.identity = None
        self.raw = b''
        self.emitted = 0
        self.partial_before = None

    def read(self):
        before = self.sample()
        self.guard.accept(before)
        with local(self.path).open('rb', buffering=0) as handle:
            info = os.fstat(handle.fileno())
            identity = (info.st_dev, info.st_ino)
            require(stat.S_ISREG(info.st_mode) and info.st_ino, 'FILE_IDENTITY')
            require(self.identity is None or self.identity == identity, 'FILE_REPLACED')
            raw = handle.read(self.limit + 1)
            after_info = os.fstat(handle.fileno())
        after = self.sample()
        self.guard.accept(after)
        current = local(self.path).stat()
        require((current.st_dev, current.st_ino) == identity, 'FILE_REPLACED')
        require(after_info.st_size >= len(raw) and len(raw) <= self.limit, 'FILE_LIMIT_OR_TRUNCATION')
        require(raw.startswith(self.raw), 'FILE_TRUNCATED_OR_PREFIX_CHANGED')
        self.identity = identity
        start = self.emitted
        rows = []
        while b'\n' in raw[start:]:
            end = raw.index(b'\n', start) + 1
            frame = raw[start:end]
            line = frame[:-1].removesuffix(b'\r')
            require(line and b'\r' not in line and len(line) <= 65536, 'INVALID_FRAME')
            low = self.partial_before if start == self.emitted and self.partial_before is not None else before['qpc_before']
            rows.append((line, start, len(frame), low, after['qpc_after']))
            start = end
        self.partial_before = ((self.partial_before if self.partial_before is not None else before['qpc_before'])
                               if start == self.emitted and start < len(raw)
                               else before['qpc_before'] if start < len(raw) else None)
        self.emitted, self.raw = start, raw
        return rows


FIELDS = set(('schema run_id native_session canonical_sequence canonical_kind canonical_file_offset '
              'canonical_frame_bytes canonical_raw_sha256 receipt_qpc_before receipt_qpc_after '
              'qpc_frequency canonical_event_time').split())


class ReceiptLedger:
    def __init__(self, path, run_id, frequency):
        require(str(UUID(run_id)) == run_id, 'RUN_ID')
        self.path, self.run_id, self.frequency = local(path), run_id, frequency
        self.rows = []
        self.failed = False
        write_new(self.path, b'')
        self.identity = self.path.stat().st_ino
        self.persisted = b''

    def observe(self, raw, offset, frame_bytes, before, after):
        require(not self.failed, 'LEDGER_FAILED')
        try:
            row = parse(raw)
            seq = row['sequence']
            require(type(seq) is int and seq >= 0, 'SEQUENCE')
            if seq < len(self.rows):
                old = self.rows[seq]
                require(old['canonical_raw_sha256'] == digest(raw)
                        and old['canonical_file_offset'] == offset
                        and old['canonical_frame_bytes'] == frame_bytes, 'CONFLICTING_DUPLICATE')
                self.verify_disk()
                return old
            entry = dict(schema='arms.diagnostic-native-receipt.v1', run_id=self.run_id,
                         native_session=row['session'], canonical_sequence=seq, canonical_kind=row['kind'],
                         canonical_file_offset=offset, canonical_frame_bytes=frame_bytes,
                         canonical_raw_sha256=digest(raw), receipt_qpc_before=before,
                         receipt_qpc_after=after, qpc_frequency=self.frequency,
                         canonical_event_time=row['event_time'])
            validate_rows(self.rows + [entry], self.run_id, self.frequency)
            self.verify_disk()
            encoded = canonical(entry) + b'\n'
            with self.path.open('ab') as handle:
                require(os.fstat(handle.fileno()).st_ino == self.identity, 'LEDGER_REPLACED')
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self.persisted += encoded
            self.rows.append(entry)
            return entry
        except Exception:
            self.failed = True
            raise

    def verify_disk(self):
        require(local(self.path).stat().st_ino == self.identity
                and self.path.read_bytes() == self.persisted, 'LEDGER_TAMPERED')


def validate_rows(rows, run_id, frequency):
    offset = 0
    previous = None
    for seq, row in enumerate(rows):
        require(set(row) == FIELDS and row['schema'] == 'arms.diagnostic-native-receipt.v1', 'LEDGER_SCHEMA')
        require(row['run_id'] == run_id and row['qpc_frequency'] == frequency, 'LEDGER_BASIS')
        require(str(UUID(row['native_session'])) == row['native_session'], 'SESSION')
        for name in ('canonical_sequence', 'canonical_file_offset', 'canonical_frame_bytes',
                     'receipt_qpc_before', 'receipt_qpc_after', 'qpc_frequency'):
            require(type(row[name]) is int, 'LEDGER_INTEGER')
        require(row['canonical_sequence'] == seq, 'SEQUENCE_GAP')
        require(row['canonical_file_offset'] == offset and row['canonical_frame_bytes'] > 0, 'OFFSET_CONFLICT')
        require(0 <= row['receipt_qpc_before'] <= row['receipt_qpc_after'], 'RECEIPT_QPC')
        if previous:
            require(row['native_session'] == previous['native_session'], 'SESSION_CHANGED')
            # Multiple records read together legitimately share the same bracket.
            require(row['receipt_qpc_before'] >= previous['receipt_qpc_before']
                    and row['receipt_qpc_after'] >= previous['receipt_qpc_after'], 'RECEIPT_REGRESSION')
        offset += row['canonical_frame_bytes']
        previous = row


def replay(ledger_raw, canonical_raw, timing_raw, run_id, frequency):
    require(ledger_raw.endswith(b'\n'), 'LEDGER_INCOMPLETE')
    rows = [parse(line) for line in ledger_raw.splitlines()]
    require(ledger_raw == b''.join(canonical(row) + b'\n' for row in rows), 'LEDGER_ENCODING')
    validate_rows(rows, run_id, frequency)
    frames = canonical_raw.splitlines(keepends=True)
    require(len(rows) == len(frames), 'MISSING_RECEIPTS')
    pairs = {p['canonical_sequence']: p for p in map(parse, timing_raw.splitlines())}
    require(len(pairs) == len(timing_raw.splitlines()), 'DUPLICATE_TIMING_PAIR')
    bindings = []
    for receipt, frame in zip(rows, frames):
        require(frame.endswith(b'\n'), 'CANONICAL_INCOMPLETE')
        raw = frame[:-1].removesuffix(b'\r')
        row = parse(raw)
        require(receipt['canonical_raw_sha256'] == digest(raw)
                and receipt['canonical_frame_bytes'] == len(frame)
                and receipt['native_session'] == row['session']
                and receipt['canonical_sequence'] == row['sequence']
                and receipt['canonical_kind'] == row['kind']
                and receipt['canonical_event_time'] == row['event_time'], 'RECEIPT_BINDING')
        if row['kind'] in ('CLOSED', 'FORMING'):
            p = pairs.pop(row['sequence'], None)
            require(p is not None and p['session'] == row['session'] and p['kind'] == row['kind']
                    and p['canonical_sha256'] == digest(raw), 'TIMING_PAIR_CONFLICT')
            require(p['emission']['qpc_after'] <= receipt['receipt_qpc_after'], 'RECEIPT_BEFORE_EMISSION')
            bindings.append(dict(canonical_sequence=row['sequence'], timing_pair_sequence=p['pair_sequence'],
                                 timing_raw_sha256=digest(timing_raw.splitlines()[p['pair_sequence']])))
    require(not pairs, 'EXTRA_TIMING_PAIR')
    return dict(schema='arms.diagnostic-receipt-summary.v1', records=len(rows), bar_bindings=bindings,
                ledger_sha256=digest(ledger_raw), runtime_admission=False,
                absolute_time_authority='UNKNOWN', data_freshness='NOT_ASSERTED')
