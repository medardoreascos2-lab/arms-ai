'''Submit one explicit operator-approved request to a local controller channel.'''

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from backend.backtesting.controller_paper_enable_command_v1 import SCHEMA
from tools import arms_one_click_runtime_phase2_v1 as phase2
from tools import arms_one_click_runtime_v1 as phase1


ZERO_AUTHORITY = {
    'paper_execution_enabled': False,
    'live_execution_allowed': False,
    'external_order_authority': False,
    'broker_live_order_authority': False,
    'ninjatrader_control_authority': False,
}


def _read(path):
    raw = path.read_bytes()
    if not 0 < len(raw) <= 8192:
        raise ValueError('COMMAND_CHANNEL_ARTIFACT_SIZE')
    value = json.loads(raw.decode('utf-8'))
    if type(value) is not dict:
        raise ValueError('COMMAND_CHANNEL_ARTIFACT_INVALID')
    return value


def request_enable(*, directory, run_id, approved, timeout=10.0,
                   clock=lambda: datetime.now(timezone.utc)):
    if approved is not True:
        raise ValueError('EXPLICIT_OPERATOR_APPROVAL_REQUIRED')
    root = Path(directory).resolve()
    channel = _read(root / 'channel.json')
    if (channel.get('status') != 'LISTENING'
            or channel.get('run_id') != run_id
            or channel.get('command') != 'ENABLE_PAPER'
            or channel.get('local_machine_only') is not True
            or channel.get('one_shot') is not True):
        raise ValueError('COMMAND_CHANNEL_NOT_AVAILABLE')
    request_id, nonce = str(uuid4()), str(uuid4())
    value = {
        'schema': SCHEMA, 'command': 'ENABLE_PAPER', 'run_id': run_id,
        'request_id': request_id, 'nonce': nonce,
        'issued_at': clock().isoformat().replace('+00:00', 'Z'),
        'explicit_operator_approval': True,
    }
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('ascii')
    request_path = root / channel['request_file']
    response_path = root / channel['response_file']
    prior_response = None
    if response_path.exists():
        info = response_path.stat()
        prior_response = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
    temporary = root / (request_path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.rename(temporary, request_path)
    finally:
        temporary.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if response_path.exists():
            info = response_path.stat()
            marker = (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
            if marker != prior_response:
                return _read(response_path)
        time.sleep(0.05)
    raise RuntimeError('COMMAND_RESPONSE_TIMEOUT')


def controlled_enable(*, run_directory, approved, timeout=10.0,
                      clock=lambda: datetime.now(timezone.utc)):
    '''Validate one sealed RUNNING_DISABLED run, then use its existing channel.'''
    if approved is not True:
        raise ValueError('EXPLICIT_OPERATOR_APPROVAL_REQUIRED')
    directory, manifest, _state, _events, validated = phase1._load_and_verify(
        run_directory)
    audit = phase1.audit(directory)
    if (audit.get('status') != 'PASS'
            or audit.get('source_binding') != phase1.SOURCE_BINDING_PASS
            or audit.get('profile_status') != 'VALID'):
        raise ValueError('SEALED_RUN_VALIDATION_FAILED')
    market = validated['profile'].get('market_identity')
    if market != phase1.REVIEWED_MARKET_IDENTITY:
        raise ValueError('REVIEWED_NQ_MARKET_IDENTITY_REQUIRED')

    runtime = phase2.status(directory)
    if runtime.get('state') != phase2.RUNNING:
        raise ValueError('RUNNING_DISABLED_REQUIRED')
    if any(runtime.get(key) is not expected
           for key, expected in ZERO_AUTHORITY.items()):
        raise ValueError('ZERO_AUTHORITY_PRECONDITION_REQUIRED')

    run_id = manifest['run_id']
    command_directory = Path(
        manifest['targets']['paper_run_namespace']).resolve() / 'controller-command-v1'
    template = validated.get('path_templates', {}).get('command_channel')
    if type(template) is not str:
        raise ValueError('REVIEWED_COMMAND_CHANNEL_REQUIRED')
    expected = phase1._absolute(
        template.replace('{RUN_ID}', run_id), base=phase1.REPO_ROOT)
    if command_directory != expected:
        raise ValueError('COMMAND_CHANNEL_BINDING_MISMATCH')

    response = request_enable(directory=command_directory, run_id=run_id,
        approved=True, timeout=timeout, clock=clock)
    post = response.get('post_enable_state') if type(response) is dict else None
    if (type(response) is not dict
            or response.get('accepted') is not True
            or response.get('reason') != 'PAPER_ENABLED'
            or type(post) is not dict
            or post.get('paper_enabled') is not True
            or post.get('paper_ready') is not True
            or post.get('readiness_blockers') != []
            or post.get('execution_mode') != 'SIMULATED / PAPER'
            or post.get('sim_execution_authority') != 'ENABLED'
            or post.get('live_execution_allowed') is not False
            or post.get('external_order_authority') is not False
            or post.get('broker_live_order_authority') is not False
            or post.get('ninjatrader_control_authority') is not False
            or post.get('thresholds_unchanged') is not True
            or post.get('risk_unchanged') is not True):
        raise RuntimeError('PAPER_ENABLE_POSTCONDITION_FAILED')
    return {
        'status': 'PAPER_ENABLED', 'run_id': run_id,
        'pre_enable_state': phase2.RUNNING,
        'paper_execution_enabled': True,
        'paper_ready': True,
        'execution_mode': 'SIMULATED / PAPER',
        'live_execution_allowed': False,
        'external_order_authority': False,
        'broker_live_order_authority': False,
        'ninjatrader_control_authority': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory', type=Path, required=True)
    parser.add_argument('--authorize-paper', action='store_true', required=True)
    parser.add_argument('--timeout', type=float, default=10.0)
    args = parser.parse_args(argv)
    response = controlled_enable(run_directory=args.run_directory,
        approved=args.authorize_paper, timeout=args.timeout)
    print(json.dumps(response, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
