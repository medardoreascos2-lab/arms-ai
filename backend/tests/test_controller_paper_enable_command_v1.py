'''Security contract for the controller-owned local PAPER command channel.'''

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.backtesting.controller_paper_enable_command_v1 import (
    ControllerPaperEnableCommandV1, REQUIRED_READINESS, SCHEMA, _atomic_replace,
)
from tools.request_current_paper_enable_v1 import request_enable
from tools.start_native_current_paper_v1 import (
    _authenticated_paper_command, _controller_paper_readiness,
)


NOW = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
RUN_ID = '20261005T060000Z-r23d-r3-test'


class Harness:
    def __init__(self):
        self.statuses = dict(REQUIRED_READINESS)
        self.blockers = ['PAPER_DISABLED']
        self.enables = 0
        self.disables = 0
        self.shutdowns = 0
        self.policy = {'risk_percent': 0.5, 'maximum_contracts': 15}

    def readiness(self):
        return {'statuses': dict(self.statuses),
            'readiness_blockers': list(self.blockers),
            '_safety_identity': ('config-id', deepcopy(self.policy))}

    def enable(self):
        self.enables += 1
        return {'paper_execution_enabled': True, 'paper_ready': True,
            'readiness_reasons': [], 'execution_kind': 'SIMULATED / PAPER',
            'live_execution_allowed': False, 'external_order_authority': False,
            'config_hash': 'config-id', 'effective_policy': deepcopy(self.policy)}

    def disable(self):
        self.disables += 1
        return {'paper_execution_enabled': False}

    def shutdown(self):
        self.shutdowns += 1


def channel(tmp_path):
    harness = Harness()
    command = ControllerPaperEnableCommandV1(
        run_id=RUN_ID, directory=tmp_path / str(uuid4()), clock=lambda: NOW,
        readiness_provider=harness.readiness, enable_call=harness.enable,
        disable_call=harness.disable, fail_closed_call=harness.shutdown,
        restrict_directory=lambda path: None,
        poll_seconds=0.01)
    return command, harness


def request(**changes):
    value = {'schema': SCHEMA, 'command': 'ENABLE_PAPER', 'run_id': RUN_ID,
        'request_id': str(uuid4()), 'nonce': str(uuid4()),
        'issued_at': NOW.isoformat().replace('+00:00', 'Z'),
        'explicit_operator_approval': True}
    value.update(changes)
    return value


def assert_rejected(command, harness, value, reason):
    result = command.handle(value)
    assert result['accepted'] is False and result['rejected'] is True
    assert result['reason'] == reason
    assert harness.enables == 0 and harness.disables == 0
    assert harness.shutdowns == 0
    return result


def test_valid_enable_is_one_shot_and_has_only_local_paper_authority(tmp_path):
    command, harness = channel(tmp_path)
    result = command.handle(request())
    assert result['accepted'] is True and harness.enables == 1
    assert set(result) == {'accepted', 'rejected', 'reason',
                           'readiness_snapshot', 'post_enable_state'}
    post = result['post_enable_state']
    assert post['paper_enabled'] is post['paper_ready'] is True
    assert post['sim_execution_authority'] == 'ENABLED'
    assert post['live_execution_allowed'] is False
    assert post['external_order_authority'] is False
    assert post['broker_live_order_authority'] is False
    assert post['thresholds_unchanged'] is post['risk_unchanged'] is True
    second = command.handle(request())
    assert second['reason'] == 'ENABLE_ALREADY_CONSUMED'
    assert harness.enables == 1


def test_wrong_run_id_has_zero_enable_side_effect(tmp_path):
    command, harness = channel(tmp_path)
    assert_rejected(command, harness, request(run_id='wrong-run'), 'RUN_ID_MISMATCH')


def test_duplicate_request_and_nonce_are_rejected_without_enable(tmp_path):
    command, harness = channel(tmp_path)
    first = request(explicit_operator_approval=False)
    assert_rejected(command, harness, first, 'EXPLICIT_OPERATOR_APPROVAL_REQUIRED')
    assert_rejected(command, harness, first, 'REQUEST_ALREADY_USED')
    second = request(nonce=first['nonce'])
    assert_rejected(command, harness, second, 'DUPLICATE_NONCE')


def test_stale_request_has_zero_enable_side_effect(tmp_path):
    command, harness = channel(tmp_path)
    issued = (NOW - timedelta(seconds=31)).isoformat().replace('+00:00', 'Z')
    assert_rejected(command, harness, request(issued_at=issued),
                    'REQUEST_STALE_OR_FUTURE')


def test_missing_approval_has_zero_enable_side_effect(tmp_path):
    command, harness = channel(tmp_path)
    assert_rejected(command, harness, request(explicit_operator_approval=False),
                    'EXPLICIT_OPERATOR_APPROVAL_REQUIRED')


@pytest.mark.parametrize('blocker', ('STALE_DATA', 'NEWS_BLOCKED'))
def test_additional_readiness_blocker_has_zero_enable_side_effect(
        tmp_path, blocker):
    command, harness = channel(tmp_path)
    harness.blockers.append(blocker)
    result = assert_rejected(command, harness, request(),
                             'SOLE_BLOCKER_NOT_PAPER_DISABLED')
    assert blocker in result['readiness_snapshot']['readiness_blockers']


@pytest.mark.parametrize('gate', ('NEWS', 'L1', 'ANALYSIS', 'SESSION_LINEAGE'))
def test_required_gate_failure_has_zero_enable_side_effect(tmp_path, gate):
    command, harness = channel(tmp_path)
    harness.statuses[gate] = 'BLOCKED'
    result = assert_rejected(command, harness, request(),
                             'REQUIRED_READINESS_FAILED')
    assert result['readiness_snapshot']['statuses'][gate] == 'BLOCKED'


def test_runtime_shutdown_and_live_command_are_inert(tmp_path):
    command, harness = channel(tmp_path)
    assert_rejected(command, harness, request(command='ENABLE_LIVE'),
                    'COMMAND_NOT_ALLOWED')
    command.close()
    assert_rejected(command, harness, request(), 'RUNTIME_SHUTDOWN')


def test_invalid_post_state_is_disabled_and_never_reports_accepted(tmp_path):
    command, harness = channel(tmp_path)
    original = harness.enable
    def unsafe():
        value = original()
        value['live_execution_allowed'] = True
        return value
    command.enable_call = unsafe
    result = command.handle(request())
    assert result['accepted'] is False
    assert result['reason'] == 'POST_ENABLE_STATE_INVALID'
    assert harness.enables == 1 and harness.disables == 1
    assert harness.shutdowns == 0


def test_ambiguous_enable_failure_disables_or_shuts_down(tmp_path):
    command, harness = channel(tmp_path)
    command.enable_call = lambda: (_ for _ in ()).throw(TimeoutError())
    result = command.handle(request())
    assert result['reason'] == 'AUTHENTICATED_PAPER_ENABLE_FAILED'
    assert harness.disables == 1 and harness.shutdowns == 0
    command, harness = channel(tmp_path)
    command.enable_call = lambda: (_ for _ in ()).throw(TimeoutError())
    command.disable_call = lambda: (_ for _ in ()).throw(TimeoutError())
    result = command.handle(request())
    assert result['reason'] == 'AUTHENTICATED_PAPER_ENABLE_FAILED'
    assert harness.shutdowns == 1


def test_file_channel_and_operator_client_round_trip_without_token(tmp_path):
    command, harness = channel(tmp_path)
    command.start()
    try:
        response = request_enable(directory=command.directory, run_id=RUN_ID,
                                  approved=True, timeout=2, clock=lambda: NOW)
        assert response['accepted'] is True and harness.enables == 1
        raw = json.dumps(response, sort_keys=True)
        assert 'admin' not in raw.lower() and 'token' not in raw.lower()
        assert not command.request_path.exists()
    finally:
        command.close()


def test_real_readiness_adapter_revalidates_every_required_source(tmp_path):
    spec = tmp_path / 'spec.json'
    spec.write_bytes(b'{}')
    session, bootstrap = str(uuid4()), object()
    adapter = SimpleNamespace(reason=None, session=session, bootstrap=bootstrap)
    runtime = SimpleNamespace(phase='AWAITING_OPERATOR_ACTIVATION', reason=None,
        adapter=adapter, bootstrap=bootstrap, bootstrap_replacement_count=1)
    lifecycle_snapshot = {'worker_alive': True, 'status': 'LIVE',
        'coordinator': {'status': 'LIVE', 'source_adapter_status': 'LIVE_TAIL',
            'bridge': {'status': 'LIVE', 'source_session': session}}}
    lifecycle = SimpleNamespace(analysis_runtime=runtime,
                                check=lambda: lifecycle_snapshot)
    news = SimpleNamespace(inspect=lambda **kwargs:
                           {'status': 'CERTIFIED_CLEAR', 'blocked': False})
    view = {'status': 'FRESH', 'provider': 'Provider31',
        'contract': 'NQ DEC26', 'instrument': 'NQ', 'quote_age_seconds': 1}
    quote = {'symbol': 'NQ', 'bid': 20000.0, 'ask': 20000.25}
    l1 = SimpleNamespace(inspect=lambda: (view, quote))
    settings = SimpleNamespace(maximum_quote_age_seconds=30,
                               maximum_spread_points=5)
    authority = SimpleNamespace(news=news, l1=l1, settings=settings)
    paper = {'readiness_reasons': ['PAPER_DISABLED'],
        'paper_execution_enabled': False, 'config_hash': 'config-id',
        'effective_policy': {'risk_percent': 0.5}}
    service = SimpleNamespace(entry_authority=authority,
        gate=SimpleNamespace(clock=lambda: NOW), get_snapshot=lambda: paper)
    result = _controller_paper_readiness(lifecycle=lifecycle, service=service,
        expected_session=session, native_spec_path=spec,
        reviewed_spec_sha256=sha256(spec.read_bytes()).hexdigest())
    assert result['statuses'] == REQUIRED_READINESS
    spec.write_bytes(b'{ }')
    result = _controller_paper_readiness(lifecycle=lifecycle, service=service,
        expected_session=session, native_spec_path=spec,
        reviewed_spec_sha256=sha256(b'{}').hexdigest())
    assert result['statuses']['NATIVE_SPEC'] == 'BLOCKED'


def test_controller_calls_only_existing_authenticated_paper_endpoint(monkeypatch):
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit):
            assert limit == 4 * 1024 * 1024 + 1
            return json.dumps({'paper_execution_enabled': True}).encode('ascii')
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'http://127.0.0.1:18016/api/v2/paper/enable'
            assert request.method == 'POST' and request.data == b'' and timeout == 3
            assert request.get_header('X-arms-admin-token') == 'process-only-secret'
            return Response()
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    result = _authenticated_paper_command(port=18016,
        token='process-only-secret', command='enable')
    assert result == {'paper_execution_enabled': True}
    with pytest.raises(ValueError, match='NOT_ALLOWED'):
        _authenticated_paper_command(port=18016,
            token='process-only-secret', command='live')
