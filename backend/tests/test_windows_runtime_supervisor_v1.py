"""Offline Windows process-tree supervision; no ARMS runtime or order path."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tools.windows_runtime_supervisor_v1 import _pid_alive, supervise


pytestmark = pytest.mark.skipif(sys.platform != 'win32',reason='Windows Job Object required')


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
    descendant=int(child_pid.read_text())
    assert descendant in report['child_pids']
    assert not _pid_alive(descendant)
    assert not _pid_alive(report['launcher_pid'])
    assert Path(report['stdout_log']).is_file()
    assert Path(report['stderr_log']).is_file()


def test_clean_exit_records_zero_without_children(tmp_path):
    report=supervise(command=[sys.executable,'-c',
        "import os,sys;assert os.environ['PYTHONFAULTHANDLER']=='1';sys.exit(0)"],
        report_directory=tmp_path/'report',run_id='offline-clean-exit',
        cwd=Path.cwd())
    assert report['windows_exit_code']==0
    assert report['windows_exit_code_hex']=='0x00000000'
    assert report['unexpected_termination'] is False
    assert report['child_cleanup_confirmed'] is True


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
