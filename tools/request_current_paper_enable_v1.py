'''Submit one explicit operator-approved request to a local controller channel.'''

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from backend.backtesting.controller_paper_enable_command_v1 import SCHEMA


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel-directory', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--approve', action='store_true', required=True)
    args = parser.parse_args(argv)
    response = request_enable(directory=args.channel_directory,
        run_id=args.run_id, approved=args.approve)
    print(json.dumps(response, sort_keys=True))
    return 0 if response.get('accepted') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
