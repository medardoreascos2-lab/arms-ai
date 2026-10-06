"""Controlled offline child failures for R24B Job Object certification."""
import argparse
import json
from pathlib import Path
import sys

from tools.windows_runtime_supervisor_v1 import _pid_alive, supervise


SCENARIOS=(('launcher',23),('backend',31),('frontend',32),('controller-child',33))


def _command(role, exit_code, pid_path):
    sleeper="import time;time.sleep(60)"
    if role=='launcher':
        return (
            "import json,subprocess,sys,time;"
            "sibling=subprocess.Popen([sys.executable,'-c',"+repr(sleeper)+"]);"
            "open("+repr(str(pid_path))+",'w').write(json.dumps({'sibling':sibling.pid}));"
            "time.sleep(.75);sys.exit("+str(exit_code)+")"
        )
    failed="import time,sys;time.sleep(.75);sys.exit("+str(exit_code)+")"
    return (
        "import json,subprocess,sys,time;"
        "failed=subprocess.Popen([sys.executable,'-c',"+repr(failed)+"]);"
        "sibling=subprocess.Popen([sys.executable,'-c',"+repr(sleeper)+"]);"
        "open("+repr(str(pid_path))+",'w').write(json.dumps("
        "{'failed':failed.pid,'sibling':sibling.pid}));"
        "code=failed.wait();time.sleep(.25);sys.exit(code)"
    )


def run(*, result_path):
    result_path=Path(result_path).resolve();root=result_path.parent
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    for role,exit_code in SCENARIOS:
        pid_path=root/('crash-'+role+'-pids.json')
        report_directory=root/('crash-'+role)
        report=supervise(command=[sys.executable,'-c',
            _command(role,exit_code,pid_path)],report_directory=report_directory,
            run_id='r24b-offline-'+role+'-failure',cwd=Path.cwd())
        pids=json.loads(pid_path.read_text())
        if (report['windows_exit_code']!=exit_code
                or not report['unexpected_termination']
                or not report['child_cleanup_confirmed']
                or any(_pid_alive(pid) for pid in pids.values())):
            raise RuntimeError('CRASH_INJECTION_FAILED:'+role)
        records.append({'role':role,'expected_exit_code':exit_code,
            'launcher_pid':report['launcher_pid'],'child_pids':report['child_pids'],
            'injected_pids':pids,'exit_code_hex':report['windows_exit_code_hex'],
            'unexpected_termination':report['unexpected_termination'],
            'child_cleanup_confirmed':report['child_cleanup_confirmed'],
            'external_report':str(report_directory/'external-shutdown-result.json'),
            'wer_report':report['wer_report'],'broker_order_calls':0})
    result={'schema':'arms.r24b.crash-injection.v1','python':sys.version,
        'scenarios':records,'all_children_cleaned':True,'broker_order_calls':0,
        'paper_enabled':False,'live_execution_allowed':False,
        'external_order_authority':False}
    result_path.write_text(json.dumps(result,sort_keys=True,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(result_path=args.result),sort_keys=True),flush=True)


if __name__=='__main__':
    main()
