"""External Windows process supervisor for one ARMS runtime tree.

Import and --help are inert. The supervisor owns one Job Object configured
with KILL_ON_JOB_CLOSE, starts only the explicit command, and writes evidence
outside the supervised Python process.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4


SCHEMA = 'arms.windows-runtime-supervisor.v1'
REPORT_SCHEMA = 'arms.external-runtime-exit.v1'
MAX_JSON_BYTES = 4 * 1024 * 1024
TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
SUPERVISOR_SPAWN_CHALLENGE_ENV = (
    'ARMS_ONE_CLICK_SUPERVISOR_SPAWN_CHALLENGE')
JobObjectExtendedLimitInformation = 9
JobObjectBasicProcessIdList = 3
MAX_JOB_PROCESSES = 4096
RECONCILE_ATTEMPTS = 20
RECONCILE_DELAY_SECONDS = 0.05


def _utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _atomic_json(path, value):
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('SUPERVISOR_REPORT_TOO_LARGE')
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path):
    if path is None:
        return None
    try:
        path = Path(path)
        size = path.stat().st_size
        if not 0 < size <= MAX_JSON_BYTES:
            return {'status': 'INVALID_SIZE'}
        raw = path.read_bytes()
        if len(raw) != size:
            return {'status': 'CHANGED_DURING_READ'}
        return json.loads(raw.decode('utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return {'status': 'UNAVAILABLE_OR_INVALID'}


def _controlled_stop_requested(path, *, run_id, supervisor_pid,
                               supervisor_identity):
    if path is None or not Path(path).exists():
        return False
    value = _read_json(path)
    expected = {
        'schema': 'arms.windows-runtime-stop-request.v1',
        'run_id': run_id,
        'supervisor_pid': supervisor_pid,
        'supervisor_identity': list(supervisor_identity),
    }
    if value != expected:
        raise RuntimeError('SUPERVISOR_STOP_REQUEST_INVALID')
    return True


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('PerProcessUserTimeLimit', ctypes.c_longlong),
        ('PerJobUserTimeLimit', ctypes.c_longlong),
        ('LimitFlags', wintypes.DWORD),
        ('MinimumWorkingSetSize', ctypes.c_size_t),
        ('MaximumWorkingSetSize', ctypes.c_size_t),
        ('ActiveProcessLimit', wintypes.DWORD),
        ('Affinity', ctypes.c_size_t),
        ('PriorityClass', wintypes.DWORD),
        ('SchedulingClass', wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ('ReadOperationCount', ctypes.c_ulonglong),
        ('WriteOperationCount', ctypes.c_ulonglong),
        ('OtherOperationCount', ctypes.c_ulonglong),
        ('ReadTransferCount', ctypes.c_ulonglong),
        ('WriteTransferCount', ctypes.c_ulonglong),
        ('OtherTransferCount', ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BasicLimitInformation', _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ('IoInfo', _IO_COUNTERS),
        ('ProcessMemoryLimit', ctypes.c_size_t),
        ('JobMemoryLimit', ctypes.c_size_t),
        ('PeakProcessMemoryUsed', ctypes.c_size_t),
        ('PeakJobMemoryUsed', ctypes.c_size_t),
    ]


def _kernel32():
    if os.name != 'nt':
        raise RuntimeError('WINDOWS_REQUIRED')
    library = ctypes.WinDLL('kernel32', use_last_error=True)
    library.CreateJobObjectW.restype = wintypes.HANDLE
    library.SetInformationJobObject.restype = wintypes.BOOL
    library.AssignProcessToJobObject.restype = wintypes.BOOL
    library.QueryInformationJobObject.restype = wintypes.BOOL
    library.TerminateJobObject.restype = wintypes.BOOL
    library.CloseHandle.restype = wintypes.BOOL
    return library


class KillOnCloseJob:
    def __init__(self):
        self.kernel = _kernel32()
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        value = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        value.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(
                self.handle, JobObjectExtendedLimitInformation,
                ctypes.byref(value), ctypes.sizeof(value)):
            error = ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def assign(self, process):
        if self.handle is None or process.poll() is not None:
            raise RuntimeError('SUPERVISED_PROCESS_NOT_LIVE')
        if not self.kernel.AssignProcessToJobObject(
                self.handle, wintypes.HANDLE(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def process_ids(self):
        if self.handle is None:
            raise RuntimeError('JOB_HANDLE_CLOSED')
        header_size = ctypes.sizeof(wintypes.DWORD) * 2
        buffer_size = header_size + (
            ctypes.sizeof(ctypes.c_size_t) * MAX_JOB_PROCESSES)
        buffer = ctypes.create_string_buffer(buffer_size)
        returned = wintypes.DWORD()
        if not self.kernel.QueryInformationJobObject(
                self.handle, JobObjectBasicProcessIdList,
                buffer, buffer_size, ctypes.byref(returned)):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned = wintypes.DWORD.from_buffer(buffer, 0).value
        count = wintypes.DWORD.from_buffer(
            buffer, ctypes.sizeof(wintypes.DWORD)).value
        if assigned > MAX_JOB_PROCESSES or count > MAX_JOB_PROCESSES:
            raise RuntimeError('JOB_PROCESS_LIMIT_EXCEEDED')
        values = (ctypes.c_size_t * count).from_buffer(buffer, header_size)
        return {int(value) for value in values}

    def terminate(self, exit_code=1):
        if self.handle is None:
            raise RuntimeError('JOB_HANDLE_CLOSED')
        if not self.kernel.TerminateJobObject(self.handle, int(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _process_table():
    kernel = _kernel32()
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    invalid = ctypes.c_void_p(-1).value
    if snapshot == invalid:
        raise ctypes.WinError(ctypes.get_last_error())
    result = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            result[int(entry.th32ProcessID)] = {
                'parent_pid': int(entry.th32ParentProcessID),
                'image': entry.szExeFile,
            }
            ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return result


def _descendants(root_pid, table=None):
    table = _process_table() if table is None else table
    found, frontier = set(), {int(root_pid)}
    while frontier:
        children = {pid for pid, value in table.items()
            if value['parent_pid'] in frontier and pid not in found}
        found.update(children)
        frontier = children
    return found


def _pid_identity(pid):
    kernel = _kernel32()
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(
        SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return None
    try:
        if kernel.WaitForSingleObject(handle, 0) != WAIT_TIMEOUT:
            return None
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel_time), ctypes.byref(user_time)):
            return None
        return (int(created.dwHighDateTime), int(created.dwLowDateTime))
    finally:
        kernel.CloseHandle(handle)


def _pid_alive(pid, identity=None):
    current = _pid_identity(pid)
    return current is not None and (identity is None or current == identity)


class ProcessIdentityLedger:
    """Immutable run ownership history keyed by PID + creation identity."""

    def __init__(self):
        self.active = {}
        self.exited = []
        self.history = []
        self.reuse_events = []

    def register(self, pid, identity):
        record = (int(pid), tuple(identity))
        previous = self.active.get(record[0])
        if previous is not None and previous != record[1]:
            raise RuntimeError('PROCESS_LEDGER_REUSE_REQUIRES_RECONCILIATION')
        if record not in self.history:
            self.history.append(record)
        self.active[record[0]] = record[1]

    def mark_exited(self, pid, identity=None):
        pid = int(pid)
        current = self.active.get(pid)
        if current is None:
            return
        if identity is not None and current != tuple(identity):
            raise RuntimeError('PROCESS_LEDGER_IDENTITY_MISMATCH')
        record = (pid, current)
        self.active.pop(pid)
        if record not in self.exited:
            self.exited.append(record)

    def accept_reuse(self, pid, old_identity, new_identity):
        pid = int(pid)
        old_identity = tuple(old_identity)
        new_identity = tuple(new_identity)
        if self.active.get(pid) != old_identity:
            raise RuntimeError('PROCESS_LEDGER_IDENTITY_MISMATCH')
        self.mark_exited(pid, old_identity)
        self.register(pid, new_identity)
        self.reuse_events.append({
            'pid': pid,
            'old_identity': list(old_identity),
            'new_identity': list(new_identity),
            'old_identity_confirmed_exited': True,
            'new_identity_confirmed_job_member': True,
        })


def _job_members(job):
    try:
        members = job.process_ids()
    except Exception as exc:
        raise RuntimeError('OWNED_JOB_MEMBERSHIP_UNAVAILABLE') from exc
    if type(members) is not set or any(
            type(pid) is not int or isinstance(pid, bool) or pid <= 0
            for pid in members):
        raise RuntimeError('OWNED_JOB_MEMBERSHIP_AMBIGUOUS')
    return members


def _reconcile_job_membership(job, ledger, *, attempts=RECONCILE_ATTEMPTS,
                              delay=RECONCILE_DELAY_SECONDS):
    """Reconcile a bounded sequence of exact Job Object membership snapshots."""
    if type(ledger) is not ProcessIdentityLedger:
        raise TypeError('PROCESS_IDENTITY_LEDGER_REQUIRED')
    if type(attempts) is not int or isinstance(attempts, bool) or attempts < 1:
        raise ValueError('RECONCILE_ATTEMPTS_INVALID')

    last_members = set()
    for attempt in range(attempts):
        members = _job_members(job)
        last_members = members
        retry = False

        for pid, old_identity in tuple(ledger.active.items()):
            if pid in members:
                continue
            current = _pid_identity(pid)
            if current is None:
                ledger.mark_exited(pid, old_identity)
            elif current != old_identity:
                raise RuntimeError('OWNED_JOB_PID_REUSE_UNOWNED')
            else:
                retry = True

        if retry:
            if attempt + 1 < attempts:
                time.sleep(delay)
                continue
            raise RuntimeError('OWNED_JOB_MEMBERSHIP_AMBIGUOUS')

        unresolved = False
        for pid in sorted(members):
            identity = _pid_identity(pid)
            if identity is None:
                unresolved = True
                continue
            previous = ledger.active.get(pid)
            if previous is None:
                ledger.register(pid, identity)
                continue
            if previous == identity:
                continue
            if _pid_alive(pid, previous):
                raise RuntimeError('OWNED_JOB_PID_REUSE_OLD_IDENTITY_ALIVE')

            confirm_members = _job_members(job)
            if pid not in confirm_members:
                ledger.mark_exited(pid, previous)
                unresolved = True
                last_members = confirm_members
                continue
            confirmed_identity = _pid_identity(pid)
            if confirmed_identity is None:
                unresolved = True
                last_members = confirm_members
                continue
            if confirmed_identity != identity:
                unresolved = True
                last_members = confirm_members
                continue
            ledger.accept_reuse(pid, previous, identity)
            if confirm_members != members:
                unresolved = True
            last_members = confirm_members

        if not unresolved:
            return last_members
        if attempt + 1 < attempts:
            time.sleep(delay)

    final_members = _job_members(job)
    for pid in final_members:
        if _pid_identity(pid) is None:
            raise RuntimeError('OWNED_JOB_PROCESS_IDENTITY_UNAVAILABLE')
    raise RuntimeError('OWNED_JOB_MEMBERSHIP_AMBIGUOUS')


def _open_bound_ports(ports):
    opened = []
    for port in sorted(set(ports)):
        if type(port) is not int or isinstance(port, bool) or not 0 < port < 65536:
            raise ValueError('OWNED_PORT_INVALID')
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(('127.0.0.1', port))
        except OSError:
            opened.append(port)
        finally:
            probe.close()
    return opened


def _owned_identity_items(owned_processes):
    if isinstance(owned_processes, ProcessIdentityLedger):
        return list(owned_processes.history)
    if type(owned_processes) is dict:
        return list(owned_processes.items())
    return list(owned_processes)


def _cleanup_evidence(*, owned_processes, job_membership, owned_ports):
    identity_items = _owned_identity_items(owned_processes)
    alive = sorted(
        {pid for pid, identity in identity_items
         if _pid_alive(pid, identity)})
    open_ports = _open_bound_ports(owned_ports)
    remaining = sorted(set(job_membership))
    confirmed = not alive and not open_ports and not remaining
    return {
        'run_scoped_process_count': len(alive),
        'run_scoped_process_pids': alive,
        'run_scoped_ports_open': len(open_ports),
        'run_scoped_open_ports': open_ports,
        'job_membership_remains': len(remaining),
        'remaining_job_member_pids': remaining,
        'cleanup_evidence_status': 'PASS' if confirmed else 'FAIL',
        'child_cleanup_confirmed': confirmed,
    }


def _wer_report(started_at, roots):
    candidates = []
    for root in roots:
        if root is None:
            continue
        try:
            root = Path(root)
            for path in root.rglob('Report.wer'):
                modified = datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc)
                if modified >= started_at:
                    candidates.append((modified, path))
        except (OSError, PermissionError):
            continue
    if not candidates:
        return None
    modified, path = max(candidates)
    return {'path': str(path.resolve()),
            'modified_utc': modified.isoformat().replace('+00:00','Z')}


def _exit_hex(code):
    return '0x' + format(int(code) & 0xffffffff, '08X')


def supervise(*, command, report_directory, run_id, cwd=None,
              health_snapshot=None, authority_snapshot=None, wer_roots=(),
              stop_request=None, spawn_challenge_sha256=None, owned_ports=()):
    if os.name != 'nt':
        raise RuntimeError('WINDOWS_REQUIRED')
    if type(command) not in (list, tuple) or not command:
        raise ValueError('EXPLICIT_COMMAND_REQUIRED')
    if type(run_id) is not str or not run_id or len(run_id) > 128:
        raise ValueError('RUN_ID_INVALID')
    report_directory = Path(report_directory).resolve()
    report_directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc)
    stdout_path = report_directory/'launcher.stdout.log'
    stderr_path = report_directory/'launcher.stderr.log'
    start_path = report_directory/'supervisor-start.json'
    report_path = report_directory/'external-shutdown-result.json'
    environment = dict(os.environ)
    environment['PYTHONFAULTHANDLER'] = '1'
    environment['PYTHONUNBUFFERED'] = '1'
    environment['ARMS_WINDOWS_JOB_SUPERVISED_V1'] = run_id
    process = None
    job = KillOnCloseJob()
    ledger = ProcessIdentityLedger()
    final_job_membership = set()
    operator_interrupt = False
    controlled_stop = False
    exit_code = None
    supervisor_identity = _pid_identity(os.getpid())
    if supervisor_identity is None:
        raise RuntimeError('SUPERVISOR_PROCESS_IDENTITY_UNAVAILABLE')
    try:
        with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
            process = subprocess.Popen(list(command),cwd=cwd,env=environment,
                stdout=stdout,stderr=stderr)
            try:
                launcher_identity = _pid_identity(process.pid)
                if launcher_identity is None:
                    raise RuntimeError('LAUNCHER_PROCESS_IDENTITY_UNAVAILABLE')
                job.assign(process)
                ledger.register(process.pid, launcher_identity)
                _atomic_json(start_path, {
                    'schema':SCHEMA,'run_id':run_id,'started_utc':_utc_now(),
                    'supervisor_pid':os.getpid(),'launcher_pid':process.pid,
                    'supervisor_identity':list(supervisor_identity),
                    'spawn_challenge_sha256':spawn_challenge_sha256,
                    'command':[str(item) for item in command],
                    'python_faulthandler':True,'kill_on_job_close':True,
                    'supervision_environment':'ARMS_WINDOWS_JOB_SUPERVISED_V1',
                })
                while True:
                    _reconcile_job_membership(job, ledger)
                    exit_code = process.poll()
                    if exit_code is not None:
                        break
                    if _controlled_stop_requested(
                            stop_request, run_id=run_id,
                            supervisor_pid=os.getpid(),
                            supervisor_identity=supervisor_identity):
                        controlled_stop = True
                        break
                    time.sleep(0.25)
            except KeyboardInterrupt:
                operator_interrupt = True
            finally:
                try:
                    _reconcile_job_membership(job, ledger)
                except RuntimeError:
                    pass
                if _job_members(job):
                    job.terminate()
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    final_job_membership = _job_members(job)
                    if not final_job_membership:
                        break
                    time.sleep(0.05)
                if process.poll() is None:
                    try:
                        exit_code = process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        exit_code = process.wait(timeout=5)
                else:
                    exit_code = process.returncode
                job.close()
    finally:
        job.close()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            alive = [pid for pid, identity in ledger.history
                     if _pid_alive(pid, identity)]
            if not alive:
                break
            time.sleep(0.05)
        for pid, identity in tuple(ledger.active.items()):
            if not _pid_alive(pid, identity):
                ledger.mark_exited(pid, identity)
        cleaned = sorted({pid for pid, identity in ledger.history
                          if not _pid_alive(pid, identity)})
        cleanup = _cleanup_evidence(
            owned_processes=ledger,
            job_membership=final_job_membership,
            owned_ports=owned_ports)
        launcher_pid = None if process is None else process.pid
        child_pids = sorted(
            {pid for pid, _identity in ledger.history if pid != launcher_pid})
        report = {
            'schema':REPORT_SCHEMA,'run_id':run_id,
            'started_utc':started_at.isoformat().replace('+00:00','Z'),
            'finished_utc':_utc_now(),'supervisor_pid':os.getpid(),
            'launcher_pid':launcher_pid,
            'child_pids':child_pids,
            'owned_processes':[
                {'pid':pid, 'identity':list(identity)}
                for pid, identity in sorted(ledger.history)],
            'process_identity_ledger': {
                'active_identities': [
                    {'pid':pid, 'identity':list(identity)}
                    for pid, identity in sorted(ledger.active.items())],
                'exited_identities': [
                    {'pid':pid, 'identity':list(identity)}
                    for pid, identity in sorted(ledger.exited)],
                'current_job_members': sorted(final_job_membership),
                'pid_reuse_events': list(ledger.reuse_events),
            },
            'windows_exit_code':exit_code,
            'windows_exit_code_hex':None if exit_code is None else _exit_hex(exit_code),
            'unexpected_termination':(
                not operator_interrupt and not controlled_stop
                and exit_code not in (0,)),
            'operator_interrupt':operator_interrupt,
            'controlled_stop_requested': controlled_stop,
            'job_kill_on_close':True,
            'cleaned_child_pids':cleaned,
            'last_health_snapshot':_read_json(health_snapshot),
            'last_authority_state':_read_json(authority_snapshot),
            'wer_report':_wer_report(started_at, wer_roots),
            'stdout_log':str(stdout_path),'stderr_log':str(stderr_path),
            **cleanup,
        }
        _atomic_json(report_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='External Windows Job Object supervisor; no trading authority.')
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--report-directory',type=Path,required=True)
    parser.add_argument('--cwd',type=Path,default=Path.cwd())
    parser.add_argument('--health-snapshot',type=Path)
    parser.add_argument('--authority-snapshot',type=Path)
    parser.add_argument('--stop-request',type=Path)
    parser.add_argument('--owned-port',type=int,action='append',default=[])
    parser.add_argument('--wer-root',type=Path,action='append',default=[])
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    command=list(args.command)
    if command and command[0]=='--':
        command=command[1:]
    if not command:
        parser.error('an explicit command is required after --')
    roots=list(args.wer_root)
    if not roots:
        for base in (os.environ.get('ProgramData'),os.environ.get('LOCALAPPDATA')):
            if base:
                roots.append(Path(base)/'Microsoft'/'Windows'/'WER'/'ReportArchive')
    spawn_challenge = os.environ.pop(SUPERVISOR_SPAWN_CHALLENGE_ENV, None)
    spawn_challenge_sha256 = (None if spawn_challenge is None else
        sha256(spawn_challenge.encode('utf-8')).hexdigest())
    report=supervise(command=command,report_directory=args.report_directory,
        run_id=args.run_id,cwd=args.cwd,health_snapshot=args.health_snapshot,
        authority_snapshot=args.authority_snapshot,wer_roots=roots,
        stop_request=args.stop_request,
        spawn_challenge_sha256=spawn_challenge_sha256,
        owned_ports=args.owned_port)
    print(json.dumps(report,sort_keys=True),flush=True)
    return 1 if report['unexpected_termination'] else 0


if __name__ == '__main__':
    sys.exit(main())
