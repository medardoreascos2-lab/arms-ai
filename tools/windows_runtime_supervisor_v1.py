"""External Windows process supervisor for one ARMS runtime tree.

Import and --help are inert. The supervisor owns one Job Object configured
with KILL_ON_JOB_CLOSE, starts only the explicit command, and writes evidence
outside the supervised Python process.
"""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
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
JobObjectExtendedLimitInformation = 9


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


def _pid_alive(pid):
    kernel = _kernel32()
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(
        SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == WAIT_TIMEOUT
    finally:
        kernel.CloseHandle(handle)


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
              health_snapshot=None, authority_snapshot=None, wer_roots=()):
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
    observed_children = set()
    operator_interrupt = False
    exit_code = None
    try:
        with stdout_path.open('xb') as stdout, stderr_path.open('xb') as stderr:
            process = subprocess.Popen(list(command),cwd=cwd,env=environment,
                stdout=stdout,stderr=stderr)
            try:
                job.assign(process)
                _atomic_json(start_path, {
                    'schema':SCHEMA,'run_id':run_id,'started_utc':_utc_now(),
                    'supervisor_pid':os.getpid(),'launcher_pid':process.pid,
                    'command':[str(item) for item in command],
                    'python_faulthandler':True,'kill_on_job_close':True,
                    'supervision_environment':'ARMS_WINDOWS_JOB_SUPERVISED_V1',
                })
                while True:
                    exit_code = process.poll()
                    try:
                        observed_children.update(_descendants(process.pid))
                    except OSError:
                        pass
                    if exit_code is not None:
                        break
                    time.sleep(0.25)
            except KeyboardInterrupt:
                operator_interrupt = True
            finally:
                job.close()
                if process.poll() is None:
                    try:
                        exit_code = process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        exit_code = process.wait(timeout=5)
                else:
                    exit_code = process.returncode
    finally:
        job.close()
        cleaned = []
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            alive = [pid for pid in observed_children if _pid_alive(pid)]
            if not alive:
                break
            time.sleep(0.05)
        cleaned = sorted(pid for pid in observed_children if not _pid_alive(pid))
        report = {
            'schema':REPORT_SCHEMA,'run_id':run_id,
            'started_utc':started_at.isoformat().replace('+00:00','Z'),
            'finished_utc':_utc_now(),'supervisor_pid':os.getpid(),
            'launcher_pid':None if process is None else process.pid,
            'child_pids':sorted(observed_children),
            'windows_exit_code':exit_code,
            'windows_exit_code_hex':None if exit_code is None else _exit_hex(exit_code),
            'unexpected_termination':(
                not operator_interrupt and exit_code not in (0,)),
            'operator_interrupt':operator_interrupt,
            'job_kill_on_close':True,
            'child_cleanup_confirmed':(
                all(not _pid_alive(pid) for pid in observed_children)),
            'cleaned_child_pids':cleaned,
            'last_health_snapshot':_read_json(health_snapshot),
            'last_authority_state':_read_json(authority_snapshot),
            'wer_report':_wer_report(started_at, wer_roots),
            'stdout_log':str(stdout_path),'stderr_log':str(stderr_path),
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
    report=supervise(command=command,report_directory=args.report_directory,
        run_id=args.run_id,cwd=args.cwd,health_snapshot=args.health_snapshot,
        authority_snapshot=args.authority_snapshot,wer_roots=roots)
    print(json.dumps(report,sort_keys=True),flush=True)
    return 1 if report['unexpected_termination'] else 0


if __name__ == '__main__':
    sys.exit(main())
