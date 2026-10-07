"""Offline Windows process-tree supervision; no ARMS runtime or order path."""
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
import time

import pytest

import tools.windows_runtime_supervisor_v1 as supervisor
from tools.windows_runtime_supervisor_v1 import _pid_alive, supervise


pytestmark = pytest.mark.skipif(sys.platform != 'win32',reason='Windows Job Object required')


class FakeJob:
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.index = 0

    def process_ids(self):
        value = self.snapshots[min(self.index, len(self.snapshots) - 1)]
        self.index += 1
        if isinstance(value, BaseException):
            raise value
        return set(value)


def test_pid_reuse_is_not_treated_as_original_child(monkeypatch):
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: (2, 2))
    assert supervisor._pid_alive(1234, (1, 1)) is False
    assert supervisor._pid_alive(1234, (2, 2)) is True


def test_exited_owned_pid_reused_inside_exact_job_is_new_identity(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: (2, 2))

    members = supervisor._reconcile_job_membership(
        FakeJob([{1234}, {1234}]), ledger, attempts=1, delay=0)

    assert members == {1234}
    assert ledger.active == {1234: (2, 2)}
    assert ledger.exited == [(1234, (1, 1))]
    assert ledger.history == [(1234, (1, 1)), (1234, (2, 2))]
    assert ledger.reuse_events == [{
        'pid': 1234,
        'old_identity': [1, 1],
        'new_identity': [2, 2],
        'old_identity_confirmed_exited': True,
        'new_identity_confirmed_job_member': True,
    }]


def test_pid_reused_outside_exact_job_fails_closed(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: (2, 2))

    with pytest.raises(RuntimeError, match='OWNED_JOB_PID_REUSE_UNOWNED'):
        supervisor._reconcile_job_membership(
            FakeJob([set()]), ledger, attempts=1, delay=0)


def test_different_identity_while_old_identity_alive_fails_closed(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: (2, 2))
    monkeypatch.setattr(supervisor, '_pid_alive', lambda _pid, _identity: True)

    with pytest.raises(
            RuntimeError, match='OWNED_JOB_PID_REUSE_OLD_IDENTITY_ALIVE'):
        supervisor._reconcile_job_membership(
            FakeJob([{1234}]), ledger, attempts=1, delay=0)


def test_pid_reuse_without_creation_identity_fails_closed(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: None)

    with pytest.raises(
            RuntimeError, match='OWNED_JOB_PROCESS_IDENTITY_UNAVAILABLE'):
        supervisor._reconcile_job_membership(
            FakeJob([{1234}, {1234}]), ledger, attempts=1, delay=0)


def test_ambiguous_job_membership_fails_closed():
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))

    with pytest.raises(RuntimeError, match='OWNED_JOB_MEMBERSHIP_UNAVAILABLE'):
        supervisor._reconcile_job_membership(
            FakeJob([OSError('membership unavailable')]),
            ledger, attempts=1, delay=0)


def test_multiple_legitimate_owned_pid_reuse_cycles(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(1234, (1, 1))
    identity = {'value': (2, 2)}
    monkeypatch.setattr(
        supervisor, '_pid_identity', lambda _pid: identity['value'])

    supervisor._reconcile_job_membership(
        FakeJob([{1234}, {1234}]), ledger, attempts=1, delay=0)
    identity['value'] = (3, 3)
    supervisor._reconcile_job_membership(
        FakeJob([{1234}, {1234}]), ledger, attempts=1, delay=0)

    assert ledger.active == {1234: (3, 3)}
    assert ledger.exited == [(1234, (1, 1)), (1234, (2, 2))]
    assert len(ledger.reuse_events) == 2


def test_ninjatrader_never_enters_identity_ledger_from_pid_churn(monkeypatch):
    ledger = supervisor.ProcessIdentityLedger()
    ledger.register(100, (1, 1))
    identities = {100: (1, 1), 1956: (9, 9)}
    monkeypatch.setattr(
        supervisor, '_pid_identity', lambda pid: identities.get(pid))

    supervisor._reconcile_job_membership(
        FakeJob([{100}]), ledger, attempts=1, delay=0)

    assert all(pid != 1956 for pid, _identity in ledger.history)


def test_cleanup_evidence_rejects_surviving_owned_identity(monkeypatch):
    monkeypatch.setattr(
        supervisor, '_pid_alive',
        lambda pid, identity: pid == 123 and identity == (1, 2))
    monkeypatch.setattr(supervisor, '_open_bound_ports', lambda _ports: [])
    evidence = supervisor._cleanup_evidence(
        owned_processes={123: (1, 2)}, job_membership=set(), owned_ports=())
    assert evidence['run_scoped_process_count'] == 1
    assert evidence['child_cleanup_confirmed'] is False
    assert evidence['cleanup_evidence_status'] == 'FAIL'


def test_cleanup_evidence_rejects_pid_reuse_as_original_identity(monkeypatch):
    monkeypatch.setattr(supervisor, '_pid_identity', lambda _pid: (9, 9))
    monkeypatch.setattr(supervisor, '_open_bound_ports', lambda _ports: [])
    evidence = supervisor._cleanup_evidence(
        owned_processes={123: (1, 2)}, job_membership=set(), owned_ports=())
    assert evidence['run_scoped_process_count'] == 0
    assert evidence['child_cleanup_confirmed'] is True


def test_job_membership_is_authoritative_even_when_process_probe_is_clear(
        monkeypatch):
    monkeypatch.setattr(supervisor, '_pid_alive', lambda _pid, _identity: False)
    monkeypatch.setattr(supervisor, '_open_bound_ports', lambda _ports: [])
    evidence = supervisor._cleanup_evidence(
        owned_processes={}, job_membership={777}, owned_ports=())
    assert evidence['job_membership_remains'] == 1
    assert evidence['child_cleanup_confirmed'] is False


def test_closed_ports_and_no_owned_processes_confirm_cleanup(monkeypatch):
    monkeypatch.setattr(supervisor, '_pid_alive', lambda _pid, _identity: False)
    monkeypatch.setattr(supervisor, '_open_bound_ports', lambda _ports: [])
    evidence = supervisor._cleanup_evidence(
        owned_processes={123: (1, 2)}, job_membership=set(),
        owned_ports=(54920, 54921, 54922))
    assert evidence == {
        'run_scoped_process_count': 0,
        'run_scoped_process_pids': [],
        'run_scoped_ports_open': 0,
        'run_scoped_open_ports': [],
        'job_membership_remains': 0,
        'remaining_job_member_pids': [],
        'cleanup_evidence_status': 'PASS',
        'child_cleanup_confirmed': True,
    }


def test_unrelated_ninjatrader_is_never_an_owned_descendant():
    table = {
        100: {'parent_pid': 1, 'image': 'python.exe'},
        101: {'parent_pid': 100, 'image': 'python.exe'},
        1956: {'parent_pid': 1, 'image': 'NinjaTrader.exe'},
    }
    assert supervisor._descendants(100, table=table) == {101}
    assert 1956 not in supervisor._descendants(100, table=table)
    evidence = supervisor._cleanup_evidence(
        owned_processes={101: (1, 1)}, job_membership=set(), owned_ports=())
    assert 1956 not in evidence['run_scoped_process_pids']


def test_unexpected_launcher_exit_kills_descendant_and_persists_report(tmp_path):
    child_pid=tmp_path/'child.pid'
    code=(
        "import os,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        f"open({str(child_pid)!r},'w').write(str(p.pid));"
        "time.sleep(.75);"
        "sys.exit(23)"
    )
    report=supervise(command=[sys.executable,'-c',code],
        report_directory=tmp_path/'report',run_id='offline-crash-injection',
        cwd=Path.cwd())
    persisted=json.loads((tmp_path/'report'/'external-shutdown-result.json').read_text())
    assert persisted==report
    assert report['windows_exit_code']==23
    assert report['windows_exit_code_hex']=='0x00000017'
    assert report['unexpected_termination'] is True
    assert report['job_kill_on_close'] is True
    assert report['child_cleanup_confirmed'] is True
    assert report['run_scoped_process_count'] == 0
    assert report['run_scoped_ports_open'] == 0
    assert report['job_membership_remains'] == 0
    assert report['cleanup_evidence_status'] == 'PASS'
    descendant=int(child_pid.read_text())
    assert descendant in report['child_pids']
    assert not _pid_alive(descendant)
    assert not _pid_alive(report['launcher_pid'])
    assert Path(report['stdout_log']).is_file()
    assert Path(report['stderr_log']).is_file()


def test_high_process_churn_cleanup_remains_complete(tmp_path):
    code = (
        "import subprocess,sys;"
        "[subprocess.run([sys.executable,'-c','pass'],check=True) "
        "for _ in range(40)]"
    )
    report = supervise(
        command=[sys.executable, '-c', code],
        report_directory=tmp_path/'high-churn-report',
        run_id='offline-high-churn', cwd=Path.cwd(),
        owned_ports=(54920, 54921, 54922))

    assert report['windows_exit_code'] == 0
    assert report['run_scoped_process_count'] == 0
    assert report['run_scoped_ports_open'] == 0
    assert report['job_membership_remains'] == 0
    assert report['child_cleanup_confirmed'] is True
    assert report['cleanup_evidence_status'] == 'PASS'
    assert report['process_identity_ledger']['current_job_members'] == []
    assert report['process_identity_ledger']['active_identities'] == []
    assert report['process_identity_ledger']['exited_identities']


def test_clean_exit_records_zero_without_children(tmp_path):
    report=supervise(command=[sys.executable,'-c',
        "import os,sys;assert os.environ['PYTHONFAULTHANDLER']=='1';sys.exit(0)"],
        report_directory=tmp_path/'report',run_id='offline-clean-exit',
        cwd=Path.cwd())
    assert report['windows_exit_code']==0
    assert report['windows_exit_code_hex']=='0x00000000'
    assert report['unexpected_termination'] is False
    assert report['child_cleanup_confirmed'] is True
    assert report['run_scoped_process_count'] == 0
    assert report['job_membership_remains'] == 0


def test_run_bound_controlled_stop_closes_only_owned_job(tmp_path):
    report_directory = tmp_path / 'report'
    stop_request = tmp_path / 'stop-request.json'

    def request_stop():
        start_path = report_directory / 'supervisor-start.json'
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if start_path.is_file():
                start = json.loads(start_path.read_text())
                supervisor._atomic_json(stop_request, {
                    'schema': 'arms.windows-runtime-stop-request.v1',
                    'run_id': 'controlled-stop-fixture',
                    'supervisor_pid': start['supervisor_pid'],
                    'supervisor_identity': start['supervisor_identity'],
                })
                return
            time.sleep(.01)
        raise AssertionError('supervisor start evidence unavailable')

    requester = Thread(target=request_stop)
    requester.start()
    report = supervise(
        command=[sys.executable, '-c', 'import time;time.sleep(60)'],
        report_directory=report_directory,
        run_id='controlled-stop-fixture', cwd=Path.cwd(),
        stop_request=stop_request)
    requester.join(timeout=10)
    assert not requester.is_alive()
    assert report['controlled_stop_requested'] is True
    assert report['unexpected_termination'] is False
    assert report['child_cleanup_confirmed'] is True
    assert not _pid_alive(report['launcher_pid'])


@pytest.mark.parametrize(('role','exit_code'), (
    ('backend', 31), ('frontend', 32), ('controller-child', 33),
))
def test_controlled_required_child_exit_is_reported_and_sibling_is_cleaned(
    tmp_path, role, exit_code,
):
    pids=tmp_path/(role+'.json')
    failed=("import time,sys;time.sleep(.75);sys.exit("+str(exit_code)+")")
    launcher=(
        "import json,subprocess,sys,time;"
        "failed=subprocess.Popen([sys.executable,'-c',"+repr(failed)+"]);"
        "sibling=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "open("+repr(str(pids))+",'w').write(json.dumps("
        "{'failed':failed.pid,'sibling':sibling.pid}));"
        "code=failed.wait();time.sleep(.25);sys.exit(code)"
    )
    report=supervise(command=[sys.executable,'-c',launcher],
        report_directory=tmp_path/('report-'+role),
        run_id='offline-'+role+'-failure',cwd=Path.cwd())
    observed=json.loads(pids.read_text())
    assert report['windows_exit_code']==exit_code
    assert report['unexpected_termination'] is True
    assert report['child_cleanup_confirmed'] is True
    assert set(observed.values()).issubset(set(report['child_pids']))
    assert all(not _pid_alive(pid) for pid in observed.values())
    assert not (tmp_path/'broker-order-call').exists()
