"""Explicit diagnostic capture CLI. Never imported by application startup.

prepare prints a NEW private exporter directory; run only observes it. Operators
add/remove their dedicated indicator manually. No absolute bounds or admission.
Structural results and overall inconclusive freshness are reported separately.

Manual sequence (do not change existing production indicator instances):
  python -B -m tools.production_capture_live_v1 prepare
  python -B -m tools.production_capture_live_v1 run --run-directory <printed-path>
  python -B -m tools.production_capture_live_v1 status --run-directory <printed-path>
Only after native_activation_allowed=true, manually add the dedicated exporter
with OutputDirectory=<printed-path>/market. At REMOVE_REQUESTED remove only that
dedicated capture instance, wait for/confirm manual removal completion, then run
acknowledge-remove --run-directory <printed-path>. Writer closure may be observed
before acknowledgement; it remains pending until the operator confirms. Keep run
alive through final artifacts. status is a saved observation, not a liveness or
readiness authority. run cannot resume or finalize an interrupted process.
"""
import argparse
from contextlib import ExitStack
import ctypes
from dataclasses import asdict
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

from tools import clock_evidence_v1 as clock
from tools import production_timing_v1 as production
from tools.production_capture_contract_v1 import Budget, Coordinator, coverage
from tools.native_timing_witness_v1 import parse, qpc_pair
from tools.native_receipt_ledger_v1 import (QpcGuard, StableFile, ReceiptLedger,
                                          canonical, digest, local, replay, require, write_new)

ROOT = Path(__file__).resolve().parents[1]
BUDGET = Budget(600, 330, 60, 30, 30)
REFERENCES = tuple(clock.REFERENCES)
SOURCES = (
    'tools/production_capture_live_v1.py', 'tools/native_receipt_ledger_v1.py',
    'tools/production_capture_contract_v1.py', 'tools/production_timing_v1.py',
    'tools/clock_evidence_v1.py', 'tools/clock_preflight_v1.py',
    'tools/native_timing_witness_v1.py',
    'backend/market_data/loaded_calendar_binding_v1.py',
    'integrations/ninjatrader/ArmsReadOnlyMarketV1.cs',
    'integrations/ninjatrader/ArmsNativeTimingWitnessV1.cs',
)


def head():
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def source_pins():
    return {name: digest((ROOT / name).read_bytes()) for name in SOURCES}


def base_directory():
    require(bool(os.environ.get('LOCALAPPDATA')), 'LOCALAPPDATA_REQUIRED')
    base = local(Path(os.environ['LOCALAPPDATA']) / 'ARMS-AI/sim-native-v3/time-review')
    require(not base.is_relative_to(ROOT), 'PRIVATE_DIRECTORY_REQUIRED')
    require(not {p.lower() for p in base.parts} &
            {'custom', 'authority-inputs', 'commands', 'activations', 'state', 'reconciliation'},
            'FORBIDDEN_OUTPUT_DIRECTORY')
    return base


def run_directory(value):
    folder = local(value)
    require(folder.parent == base_directory() and str(UUID(folder.name)) == folder.name, 'PRIVATE_RUN_PATH')
    return folder


def write_json(path, value):
    write_new(path, canonical(value) + b'\n')


def replace_status(folder, value):
    target = local(folder / 'status.json')
    temp = folder / 'status.next'
    write_json(temp, value)
    os.replace(temp, target)


def prepare():
    initial = qpc_pair()
    QpcGuard(initial['frequency']).accept(initial)
    run_id = str(uuid4())
    base = base_directory()
    base.mkdir(parents=True, exist_ok=True)
    folder = base / run_id
    folder.mkdir()  # Never reuse or resume a directory.
    for name in ('market', 'receipts', 'clock', 'clock/measurements', 'final'):
        (folder / name).mkdir()
    manifest = dict(schema='arms.diagnostic-capture-run.v1', run_id=run_id, epoch=run_id,
                    qpc_frequency=initial['frequency'], initial_qpc=initial,
                    pid=os.getpid(), python_executable=sys.executable, repo_head=head(),
                    source_sha256=source_pins(), budget=asdict(BUDGET), references=list(REFERENCES),
                    exporter_directory=str(folder / 'market'), runtime_admission=False,
                    boot_identity='NOT_ATTESTED', absolute_time_authority='UNKNOWN')
    write_json(folder / 'run.json', manifest)
    replace_status(folder, dict(state='PREPARED', run_id=run_id, runtime_admission=False))
    return folder


def load_run(folder):
    folder = run_directory(folder)
    manifest = parse(local(folder / 'run.json').read_bytes())
    require(manifest['run_id'] == folder.name and manifest['epoch'] == folder.name
            and manifest['runtime_admission'] is False, 'RUN_MANIFEST')
    require(manifest['repo_head'] == head() and manifest['source_sha256'] == source_pins(), 'SOURCE_PIN_CHANGED')
    require(manifest['budget'] == asdict(BUDGET) and manifest['references'] == list(REFERENCES)
            and manifest['exporter_directory'] == str(folder / 'market'), 'RUN_CONFIGURATION_CHANGED')
    return folder, manifest


def acknowledge(folder):
    folder, manifest = load_run(folder)
    request = parse(local(folder / 'remove-request.json').read_bytes())
    status = parse(local(folder / 'status.json').read_bytes())
    require(status['state'] == 'REMOVE_REQUESTED' and request['run_id'] == manifest['run_id']
            and request['request_id'] == status['request_id'], 'NO_ACTIVE_REMOVE_REQUEST')
    pair = qpc_pair()
    QpcGuard(manifest['qpc_frequency'], request['request_qpc']).accept(pair)
    write_json(folder / 'remove-ack.json', dict(run_id=manifest['run_id'], request_id=request['request_id'],
               native_session=request['native_session'], qpc=pair,
               statement='I received and completed the manual remove request.', native_closure=False))


class ClockCollector:
    """One serial worker, all attempts retained. Main loop remains deadline driven.

    Raw probe perf-counter fields remain the existing probe's internal measurements;
    only qpc_pair bridges are used as the shared native/Python QPC basis.
    """
    def __init__(self, folder, run_id, frequency):
        self.folder, self.run_id = folder, run_id
        self.guard = QpcGuard(frequency)
        self.stop = threading.Event()
        self.items = queue.Queue()
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.error = None

    def attempt(self, reference):
        require(reference in REFERENCES, 'REFERENCE_NOT_ALLOWLISTED')
        before = qpc_pair()
        self.guard.accept(before)
        try:
            address = clock.resolve(reference)
        except (OSError, ValueError, subprocess.SubprocessError):
            raw = canonical(dict(reference=reference, epoch=self.run_id, status='PROBE_INVALID_OR_UNAVAILABLE'))
            after = qpc_pair()
            bridge = dict(before=before, after=after, measurement_sha256=digest(raw))
        else:
            raw, bridge = production.acquire_clock_measurement(reference, address, self.run_id)
            self.guard.accept(bridge['before'])
        self.guard.accept(bridge['after'])
        require(digest(raw) == bridge['measurement_sha256'], 'MEASUREMENT_HASH')
        return raw, bridge

    def work(self):
        index = 0
        try:
            while not self.stop.is_set():
                for reference in REFERENCES:
                    if self.stop.is_set():
                        return
                    raw, bridge = self.attempt(reference)
                    prefix = self.folder / 'clock/measurements' / f'{index:05d}'
                    write_new(prefix.with_suffix('.json'), raw)
                    write_json(prefix.with_suffix('.bridge.json'), bridge)
                    self.items.put((index, raw, bridge))
                    index += 1
                self.stop.wait(1)
        except Exception as error:
            self.error = type(error).__name__ + ':' + str(error)


def exclusive_bytes(paths):
    """Windows read-only share=0 handles prove writers are closed while read.

    All handles remain open together. A seal alone or an operator ack is not closure.
    """
    require(os.name == 'nt', 'WINDOWS_REQUIRED')
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                       ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    create.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    with ExitStack() as stack:
        handles = []
        for path in paths:
            handle = create(str(local(path)), 0x80000000, 0, None, 3, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                code = ctypes.get_last_error()
                if code in (32, 33):
                    return None
                raise OSError(code, 'EXCLUSIVE_READ_FAILED')
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            except Exception:
                kernel.CloseHandle(handle)
                raise
            handles.append(stack.enter_context(os.fdopen(fd, 'rb')))
        result = tuple(h.read(production.MAX_BYTES + 1) for h in handles)
        require(all(len(raw) <= production.MAX_BYTES for raw in result), 'NATIVE_FILE_LIMIT')
        return result


class NativeMonitor:
    def __init__(self, folder, run_id, frequency):
        self.folder, self.frequency = folder, frequency
        self.ledger = ReceiptLedger(folder / 'receipts/records.jsonl', run_id, frequency)
        self.files = {}
        self.session = None
        self.closed = 0
        self.sealed = None
        self.paths = None
        self.frozen_native = None

    def poll(self):
        market = local(self.folder / 'market')
        candidates = [p for p in market.glob('*.jsonl') if not p.name.endswith('.connection.jsonl')]
        require(len(candidates) <= 1, 'MULTIPLE_CANONICAL_SESSIONS')
        if not candidates:
            require(self.session is None, 'CANONICAL_DISAPPEARED')
            return None
        path = candidates[0]
        session = path.stem
        require(str(UUID(session)) == session and self.session in (None, session), 'SESSION_CHANGED')
        self.session = session
        timing = market / 'timing' / (session + '.production-timing.jsonl')
        seal = Path(str(timing) + '.done.json')
        self.paths = (path, timing, seal)
        allowed = {path, market / (session + '.connection.jsonl'), timing,
                   seal, Path(str(timing) + '.done.tmp')}
        actual = set(p for p in market.rglob('*') if p.is_file())
        require(actual <= allowed, 'UNEXPECTED_NATIVE_FILE')
        if self.frozen_native is not None:
            require(actual == set(self.frozen_native), 'SEALED_NATIVE_INVENTORY_CHANGED')
            for p, (identity, raw) in self.frozen_native.items():
                info = local(p).stat()
                require((info.st_dev, info.st_ino) == identity and p.read_bytes() == raw, 'SEALED_FILES_CHANGED')
        for p in actual:
            local(p)
        for p in market.rglob('*'):
            local(p)
        for p in list(self.files):
            require(p.exists(), 'NATIVE_FILE_DISAPPEARED')
        connection = market / (session + '.connection.jsonl')
        for p in (path, timing, connection):
            if p.exists():
                tail = self.files.setdefault(p, StableFile(p, self.frequency))
                rows = tail.read()
                if p == path:
                    for raw, offset, size, before, after in rows:
                        row = self.ledger.observe(raw, offset, size, before, after)
                        require(row['native_session'] == session, 'SESSION_CHANGED')
                        if row['canonical_kind'] == 'CLOSED':
                            self.closed += 1
        if timing in self.files:
            pairs = self.files[timing].raw[:self.files[timing].emitted].splitlines()
            canonical_rows = self.ledger.rows
            seen = set()
            for index, raw in enumerate(pairs):
                p = parse(raw)
                seq = p['canonical_sequence']
                require(type(seq) is int and seq >= 0 and seq not in seen
                        and p['pair_sequence'] == index and p['session'] == session
                        and p['qpc_frequency'] == self.frequency, 'TIMING_PAIR_CONFLICT')
                seen.add(seq)
                # The timing file may grow just after the canonical read. Defer
                # missing rows until the next poll; never infer their receipt.
                if seq < len(canonical_rows):
                    row = canonical_rows[seq]
                    require(p['kind'] in ('CLOSED', 'FORMING') and p['kind'] == row['canonical_kind']
                            and p['canonical_sha256'] == row['canonical_raw_sha256'], 'TIMING_PAIR_CONFLICT')
        self.ledger.verify_disk()
        if seal.exists():
            if seal not in self.files:
                self.files[seal] = StableFile(seal, self.frequency, limit=4096)
            self.files[seal].read()
            sealed = exclusive_bytes(self.paths)
            if sealed is not None:
                require(all(self.files[p].raw == raw for p, raw in zip(self.paths, sealed)), 'SEALED_READ_CHANGED')
                require(self.sealed in (None, sealed), 'SEALED_FILES_CHANGED')
                self.sealed = sealed
                if self.frozen_native is None:
                    require(Path(str(timing) + '.done.tmp') not in actual, 'SEAL_PUBLICATION_INCOMPLETE')
                    self.frozen_native = {p: ((p.stat().st_dev, p.stat().st_ino), p.read_bytes()) for p in actual}
                return sealed
        return None


class LiveAdapter:
    """I/O wrapper; all deadline and state transitions belong to Coordinator."""
    def __init__(self, folder, manifest, ready):
        self.folder, self.manifest = folder, manifest
        self.guard = QpcGuard(manifest['qpc_frequency'], manifest['initial_qpc']['qpc_after'])
        self.guard.accept(ready)
        self.engine = Coordinator(run_id=manifest['run_id'], epoch=manifest['run_id'],
                                  frequency=ready['frequency'], ready_qpc=ready['qpc_after'], budget=BUDGET)
        self.ack_raw = None

    def step(self, pair, *, session=None, closed=0, sealed=None, collector_alive=True):
        c = self.engine
        if c.state in ('FAILED', 'COMPLETE'):
            return c.snapshot()
        try:
            self.guard.accept(pair)
            ack = None
            ack_path = self.folder / 'remove-ack.json'
            if ack_path.exists():
                raw = local(ack_path).read_bytes()
                require(self.ack_raw in (None, raw), 'ACK_CHANGED')
                row = parse(raw)
                require(row['run_id'] == c.run_id and row['native_session'] == c.session
                        and row['native_closure'] is False,
                        'REQUEST_ACK_IDENTITY' if c.pending_closure else 'WRONG_REMOVE_ACK')
                require(row['request_id'] == c.request_id, 'REQUEST_ACK_IDENTITY')
                QpcGuard(c.frequency, c.request_qpc).accept(row['qpc'])
                require(row['qpc']['qpc_after'] <= pair['qpc_before'], 'FUTURE_ACK')
                self.ack_raw = raw
                ack = row['request_id']
            result = c.tick(pair['qpc_after'], epoch=c.epoch, frequency=pair['frequency'],
                            session=session, closed=closed, sealed=sealed, exclusive_closed=sealed is not None,
                            collector_alive=collector_alive, acknowledged_request=ack)
            if c.state == 'REMOVE_REQUESTED' and not (self.folder / 'remove-request.json').exists():
                write_json(self.folder / 'remove-request.json', dict(run_id=c.run_id, request_id=c.request_id,
                           native_session=c.session, request_qpc=c.request_qpc,
                           instructions='Remove only the dedicated ArmsReadOnlyMarketV1 capture instance'))
            elif (self.folder / 'remove-request.json').exists():
                request = parse(local(self.folder / 'remove-request.json').read_bytes())
                require(request == dict(run_id=c.run_id, request_id=c.request_id, native_session=c.session,
                                        request_qpc=c.request_qpc,
                                        instructions='Remove only the dedicated ArmsReadOnlyMarketV1 capture instance'),
                        'REMOVE_REQUEST_CHANGED')
            replace_status(self.folder, result)
            return result
        except Exception as error:
            c.fail(str(error))
            replace_status(self.folder, c.snapshot())
            return c.snapshot()


def inventory(folder):
    result = {}
    for path in sorted(folder.rglob('*')):
        local(path)
        if path.is_file() and path != folder / 'final/capture-manifest.json':
            result[path.relative_to(folder).as_posix()] = dict(bytes=path.stat().st_size, sha256=digest(path.read_bytes()))
    return result


def validate_clock_artifacts(folder, attempts, run_id, frequency):
    """Retain and verify every attempt, including invalid/unavailable probes."""
    guard = QpcGuard(frequency)
    expected = set()
    for expected_index, (index, raw, bridge) in enumerate(attempts):
        require(index == expected_index, 'CLOCK_INVENTORY_GAP')
        prefix = folder / 'clock/measurements' / f'{index:05d}'
        paths = (prefix.with_suffix('.json'), prefix.with_suffix('.bridge.json'))
        expected.update(paths)
        require(local(paths[0]).read_bytes() == raw
                and local(paths[1]).read_bytes() == canonical(bridge)+b'\n'
                and digest(raw) == bridge['measurement_sha256'], 'CLOCK_ARTIFACT_CHANGED')
        row = parse(raw)
        require(row['epoch'] == run_id and row['reference'] == REFERENCES[index % len(REFERENCES)], 'CLOCK_INVENTORY_IDENTITY')
        guard.accept(bridge['before'])
        guard.accept(bridge['after'])
        if row['status'] == 'MEASURED_NOT_ATTESTED':
            decoded = clock.decode_reply(bytes.fromhex(row['packet_hex']), clock.encode_time(row['sent']['host_ns']),
                                         row['sent'], row['received'], row['reference'], run_id)
            require(decoded == row, 'CLOCK_PACKET_REPLAY')
        else:
            require(row['status'] == 'PROBE_INVALID_OR_UNAVAILABLE', 'CLOCK_STATUS')
    require(set((folder / 'clock/measurements').iterdir()) == expected, 'CLOCK_INVENTORY_FILES')


def run(folder):
    folder, manifest = load_run(folder)
    require(not any((folder / 'market').iterdir()), 'NATIVE_CAPTURE_ALREADY_STARTED')
    write_json(folder / 'run-start.json', dict(pid=os.getpid(), qpc=qpc_pair(), runtime_admission=False))
    write_json(folder / 'clock/windows-before.json', clock.windows_snapshot())
    collector = ClockCollector(folder, folder.name, manifest['qpc_frequency'])
    monitor = NativeMonitor(folder, folder.name, manifest['qpc_frequency'])
    attempts = []
    adapter = LiveAdapter(folder, manifest, qpc_pair())
    c = adapter.engine
    native_ready = False
    collector.thread.start()
    try:
        while c.state not in ('FAILED', 'COMPLETE'):
            while True:
                try:
                    attempts.append(collector.items.get_nowait())
                except queue.Empty:
                    break
            if not native_ready:
                require(not any((folder / 'market').iterdir()), 'NATIVE_ACTIVATION_BEFORE_CLOCK_READY')
                native_ready = set(parse(raw)['reference'] for _, raw, _ in attempts) == set(REFERENCES)
            sealed = monitor.poll() if native_ready else None
            adapter.step(qpc_pair(), session=monitor.session, closed=monitor.closed, sealed=sealed,
                         collector_alive=collector.thread.is_alive() and collector.error is None)
            if c.state == 'WAITING_FOR_ACTIVATION':
                replace_status(folder, dict(**c.snapshot(), native_activation_allowed=native_ready,
                                           exporter_directory=str(folder / 'market')))
            if c.state == 'FINAL_CLOCK':
                valid = [(raw, bridge) for _, raw, bridge in attempts
                         if parse(raw).get('status') == 'MEASURED_NOT_ATTESTED']
                raws, bridges = [x[0] for x in valid], [x[1] for x in valid]
                # Wait for final attempts from every reference; do not finish early.
                if all(any(parse(raw)['reference'] == ref and b['before']['qpc_before'] >= c.closure_qpc
                           for _, raw, b in attempts) for ref in REFERENCES):
                    try:
                        coverage(c.proof, run_id=c.run_id, references=REFERENCES, measurements=raws,
                                 bridges=bridges, closure_qpc=c.closure_qpc)
                    except ValueError:
                        # Unavailable probes are inconclusive, not favorable selection.
                        if any(parse(raw).get('status') != 'MEASURED_NOT_ATTESTED' for _, raw, _ in attempts):
                            c.fail('REFERENCE_EVIDENCE_INCOMPLETE')
                        else:
                            c.fail('CLOCK_COVERAGE_UNPROVEN')
                    else:
                        unchanged = monitor.poll() == monitor.sealed
                        p = qpc_pair()
                        adapter.guard.accept(p)
                        c.finish(qpc=p['qpc_after'], epoch=c.epoch, frequency=p['frequency'],
                                 measurements=raws, bridges=bridges, references=REFERENCES,
                                 unchanged_closed=unchanged)
            if c.state not in ('FAILED', 'COMPLETE'):
                time.sleep(0.1)
    except Exception as error:
        c.fail(type(error).__name__ + ':' + str(error))
    finally:
        collector.stop.set()
        collector.thread.join(6)
        if collector.thread.is_alive() or collector.error:
            c.fail('CLOCK_WORKER_FAILURE')
    while not collector.items.empty():
        attempts.append(collector.items.get_nowait())
    write_json(folder / 'clock/windows-after.json', clock.windows_snapshot())
    proof = production.adjudicate(*monitor.sealed) if monitor.sealed else dict(status='FAIL', reason='NO_SEALED_STREAM')
    receipt = dict(status='INCONCLUSIVE', reason='NO_SEALED_STREAM', runtime_admission=False)
    try:
        require(head() == manifest['repo_head'] and source_pins() == manifest['source_sha256'], 'SOURCE_PIN_CHANGED')
        require(parse((folder / 'run.json').read_bytes()) == manifest, 'RUN_MANIFEST_CHANGED')
        validate_clock_artifacts(folder, attempts, c.run_id, c.frequency)
        monitor.ledger.verify_disk()
        if monitor.sealed:
            require(monitor.poll() == monitor.sealed, 'SEALED_FILES_CHANGED')
            receipt = replay(monitor.ledger.path.read_bytes(), *monitor.sealed[:2], c.run_id, c.frequency)
    except Exception as error:
        c.fail(str(error))
    write_json(folder / 'final/production-adjudication.json', proof)
    write_json(folder / 'final/receipt-ledger.json', receipt)
    write_new(folder / 'final/receipt-ledger.sha256', (digest(monitor.ledger.path.read_bytes()) + '\n').encode())
    write_json(folder / 'final/clock-inventory.json', [dict(index=i, status=parse(raw)['status'],
               reference=parse(raw)['reference'], measurement_sha256=digest(raw), bridge=bridge)
               for i, raw, bridge in attempts])
    write_json(folder / 'final/coverage.json', c.binding or dict(status='INCONCLUSIVE', reason=c.reason))
    valid = [(raw, bridge) for _, raw, bridge in attempts if parse(raw).get('status') == 'MEASURED_NOT_ATTESTED']
    binding = dict(status='INCONCLUSIVE', runtime_admission=False)
    if proof['status'] == 'PASS' and valid:
        try:
            binding = production.clock_epoch_binding(proof, run_id=c.run_id, epoch=c.run_id,
                       measurements=[r for r, _ in valid], bridges=[b for _, b in valid])
        except ValueError as error:
            binding['reason'] = str(error)
    write_json(folder / 'final/clock-binding.json', binding)
    write_json(folder / 'final/coordinator.json', dict(snapshot=c.snapshot(), events=c.events))
    structural = 'STRUCTURAL_PASS' if c.state == 'COMPLETE' else (
        'INCONCLUSIVE' if c.reason in ('MINIMUM_CLOSED_NOT_OBSERVED', 'REFERENCE_EVIDENCE_INCOMPLETE') else 'FAIL')
    result = dict(result='FAIL' if structural == 'FAIL' else 'INCONCLUSIVE', structural_result=structural,
                  reason=c.reason, run_id=c.run_id, runtime_admission=False,
                  source_time_recency='UNKNOWN', absolute_market_recency='UNKNOWN',
                  absolute_time_authority='UNKNOWN', data_freshness='NOT_ASSERTED',
                  reviewed_bounds=None)
    replace_status(folder, result)
    write_json(folder / 'final/capture-manifest.json', dict(schema='arms.diagnostic-capture-manifest.v1',
               **result, repo_head=manifest['repo_head'], source_sha256=manifest['source_sha256'],
               artifacts=inventory(folder)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('prepare')
    for name in ('run', 'status', 'acknowledge-remove'):
        commands.add_parser(name).add_argument('--run-directory', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare())
    elif args.command == 'run':
        print(canonical(run(args.run_directory)).decode())
    elif args.command == 'acknowledge-remove':
        acknowledge(args.run_directory)
    else:
        folder = run_directory(args.run_directory)
        print(local(folder / 'status.json').read_text())


if __name__ == '__main__':
    main()
