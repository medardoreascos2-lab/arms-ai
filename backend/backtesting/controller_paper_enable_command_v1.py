'''Private, run-scoped, one-shot local PAPER controller command.'''

from copy import deepcopy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
from threading import Event, RLock, Thread
from uuid import UUID, uuid4

SCHEMA = 'arms.controller-paper-enable-command.v1'
CHANNEL_SCHEMA = 'arms.controller-paper-enable-channel.v1'
MAX_REQUEST_BYTES = 8192
MAX_REQUEST_AGE = timedelta(seconds=30)
MAX_FUTURE_SKEW = timedelta(seconds=2)
REQUIRED_READINESS = {
    'NATIVE_SPEC': 'PASS', 'NEWS': 'PASS', 'CATCHUP': 'PASS_CERTIFIED',
    'LIVE_STREAM': 'PASS', 'L1': 'PASS', 'ANALYSIS': 'PASS',
    'SESSION_LINEAGE': 'PASS',
}
REQUEST_FIELDS = {'schema', 'command', 'run_id', 'request_id', 'nonce',
                  'issued_at', 'explicit_operator_approval'}


def _atomic_replace(path, value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('ascii')
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _utc(value):
    if type(value) is not str or not value.endswith('Z'):
        raise ValueError('REQUEST_TIME_INVALID')
    parsed = datetime.fromisoformat(value[:-1] + '+00:00')
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError('REQUEST_TIME_INVALID')
    return parsed


def _uuid(value, reason):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValueError(reason) from None
    return value


class ControllerPaperEnableCommandV1:
    '''Consume local requests while allowing at most one enable attempt.'''

    def __init__(self, *, run_id, directory, clock, readiness_provider,
                 enable_call, disable_call, fail_closed_call, restrict_directory,
                 poll_seconds=0.05):
        if (type(run_id) is not str
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', run_id)):
            raise ValueError('RUN_ID_INVALID')
        dependencies = (clock, readiness_provider, enable_call, disable_call,
                        fail_closed_call, restrict_directory)
        if not all(callable(value) for value in dependencies):
            raise TypeError('COMMAND_DEPENDENCY_REQUIRED')
        if (type(poll_seconds) not in (int, float)
                or isinstance(poll_seconds, bool)
                or not 0.01 <= poll_seconds <= 1.0):
            raise ValueError('COMMAND_POLL_INTERVAL_INVALID')

        self.run_id = run_id
        self.directory = Path(directory).resolve()
        self.request_path = self.directory / 'request.json'
        self.response_path = self.directory / 'response.json'
        self.channel_path = self.directory / 'channel.json'
        self.clock = clock
        self.readiness_provider = readiness_provider
        self.enable_call = enable_call
        self.disable_call = disable_call
        self.fail_closed_call = fail_closed_call
        self.poll_seconds = float(poll_seconds)
        self.lock = RLock()
        self.stop_event = Event()
        self.thread = None
        self.started = False
        self.closed = False
        self.worker_error = None
        self.enable_consumed = False
        self.seen_request_ids = set()
        self.seen_nonces = set()

        self.directory.mkdir(parents=False, exist_ok=False)
        restrict_directory(self.directory)
        self._write_channel('CREATED')

    def _write_channel(self, status):
        _atomic_replace(self.channel_path, {
            'schema': CHANNEL_SCHEMA, 'run_id': self.run_id,
            'command': 'ENABLE_PAPER', 'request_file': self.request_path.name,
            'response_file': self.response_path.name, 'one_shot': True,
            'local_machine_only': True, 'status': status,
        })

    @staticmethod
    def _response(*, accepted, reason, request_id=None, readiness=None, post=None):
        return {
            'accepted': accepted is True, 'rejected': accepted is not True,
            'reason': reason,
            'readiness_snapshot': deepcopy(readiness),
            'post_enable_state': deepcopy(post),
        }

    def _reject(self, reason, *, request_id=None, readiness=None, post=None):
        return self._response(accepted=False, reason=reason,
            request_id=request_id, readiness=readiness, post=post)

    def _revoke_enable(self):
        try:
            disabled = self.disable_call()
            if (type(disabled) is not dict
                    or disabled.get('paper_execution_enabled') is not False):
                raise RuntimeError('PAPER_DISABLE_NOT_CONFIRMED')
        except Exception:
            self.fail_closed_call()

    @staticmethod
    def _public_readiness(value):
        statuses = value.get('statuses', {}) if type(value) is dict else {}
        blockers = value.get('readiness_blockers', []) if type(value) is dict else []
        return {
            'statuses': {key: statuses.get(key, 'BLOCKED')
                         for key in REQUIRED_READINESS},
            'readiness_blockers': (list(blockers)
                                   if type(blockers) is list else ['INVALID']),
        }

    @staticmethod
    def _post_state(value, *, safety_unchanged):
        if type(value) is not dict:
            return None
        enabled = value.get('paper_execution_enabled') is True
        ready = value.get('paper_ready') is True
        reasons = value.get('readiness_reasons')
        paper = enabled and ready and reasons == []
        return {
            'paper_enabled': enabled,
            'paper_ready': ready,
            'readiness_blockers': (list(reasons)
                                   if type(reasons) is list else ['INVALID']),
            'execution_mode': value.get('execution_kind'),
            'sim_execution_authority': 'ENABLED' if paper else 'DISABLED',
            'live_execution_allowed': False,
            'external_order_authority': False,
            'broker_live_order_authority': False,
            'thresholds_unchanged': safety_unchanged,
            'risk_unchanged': safety_unchanged,
        }

    def handle(self, request):
        '''Validate one request and perform at most one authenticated enable.'''
        with self.lock:
            request_id = request.get('request_id') if type(request) is dict else None
            if self.closed:
                return self._reject('RUNTIME_SHUTDOWN', request_id=request_id)
            if type(request) is not dict or set(request) != REQUEST_FIELDS:
                return self._reject('REQUEST_SCHEMA_INVALID', request_id=request_id)
            try:
                request_id = _uuid(request['request_id'], 'REQUEST_ID_INVALID')
                nonce = _uuid(request['nonce'], 'NONCE_INVALID')
            except ValueError as error:
                return self._reject(str(error), request_id=request_id)
            if request_id in self.seen_request_ids:
                return self._reject('REQUEST_ALREADY_USED', request_id=request_id)
            if nonce in self.seen_nonces:
                return self._reject('DUPLICATE_NONCE', request_id=request_id)
            self.seen_request_ids.add(request_id)
            self.seen_nonces.add(nonce)
            if self.enable_consumed:
                return self._reject('ENABLE_ALREADY_CONSUMED', request_id=request_id)
            if request['schema'] != SCHEMA or request['command'] != 'ENABLE_PAPER':
                return self._reject('COMMAND_NOT_ALLOWED', request_id=request_id)
            if request['run_id'] != self.run_id:
                return self._reject('RUN_ID_MISMATCH', request_id=request_id)
            if request['explicit_operator_approval'] is not True:
                return self._reject('EXPLICIT_OPERATOR_APPROVAL_REQUIRED',
                                    request_id=request_id)
            try:
                issued = _utc(request['issued_at'])
                now = self.clock()
                if now.tzinfo is None or now.utcoffset() != timedelta(0):
                    raise ValueError('CONTROLLER_CLOCK_INVALID')
                age = now - issued
                if age > MAX_REQUEST_AGE or age < -MAX_FUTURE_SKEW:
                    raise ValueError('REQUEST_STALE_OR_FUTURE')
            except (ValueError, TypeError, OverflowError):
                return self._reject('REQUEST_STALE_OR_FUTURE',
                                    request_id=request_id)

            try:
                readiness = self.readiness_provider()
            except Exception:
                return self._reject('READINESS_REVALIDATION_FAILED',
                                    request_id=request_id)
            public = self._public_readiness(readiness)
            statuses = readiness.get('statuses', {}) if type(readiness) is dict else {}
            blockers = (readiness.get('readiness_blockers')
                        if type(readiness) is dict else None)
            if any(statuses.get(key) != expected
                   for key, expected in REQUIRED_READINESS.items()):
                return self._reject('REQUIRED_READINESS_FAILED',
                    request_id=request_id, readiness=public)
            if blockers != ['PAPER_DISABLED']:
                return self._reject('SOLE_BLOCKER_NOT_PAPER_DISABLED',
                    request_id=request_id, readiness=public)

            safety_identity = readiness.get('_safety_identity')
            self.enable_consumed = True
            try:
                enabled = self.enable_call()
            except Exception:
                self._revoke_enable()
                return self._reject('AUTHENTICATED_PAPER_ENABLE_FAILED',
                    request_id=request_id, readiness=public)
            safety_unchanged = (
                type(enabled) is dict and safety_identity is not None
                and safety_identity == (enabled.get('config_hash'),
                                        enabled.get('effective_policy')))
            post = self._post_state(enabled, safety_unchanged=safety_unchanged)
            valid_post = (
                post is not None and post['paper_enabled'] is True
                and post['paper_ready'] is True
                and post['readiness_blockers'] == []
                and post['execution_mode'] == 'SIMULATED / PAPER'
                and post['sim_execution_authority'] == 'ENABLED'
                and post['live_execution_allowed'] is False
                and post['external_order_authority'] is False
                and post['broker_live_order_authority'] is False
                and post['thresholds_unchanged'] is True
                and post['risk_unchanged'] is True
                and enabled.get('live_execution_allowed') is False
                and enabled.get('external_order_authority', False) is False)
            if not valid_post:
                self._revoke_enable()
                return self._reject('POST_ENABLE_STATE_INVALID',
                    request_id=request_id, readiness=public, post=post)
            return self._response(accepted=True, reason='PAPER_ENABLED',
                request_id=request_id, readiness=public, post=post)

    @staticmethod
    def _invalid_json():
        raise ValueError('NONFINITE_JSON')

    @staticmethod
    def _unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('DUPLICATE_FIELD')
            value[key] = item
        return value

    def _read_request(self):
        try:
            size = self.request_path.stat().st_size
            if not 0 < size <= MAX_REQUEST_BYTES:
                raise ValueError('REQUEST_SIZE_INVALID')
            with self.request_path.open('rb') as stream:
                raw = stream.read(MAX_REQUEST_BYTES + 1)
            if len(raw) != size or len(raw) > MAX_REQUEST_BYTES:
                raise ValueError('REQUEST_SIZE_INVALID')
            return json.loads(raw.decode('utf-8'), object_pairs_hook=self._unique,
                parse_constant=lambda _: self._invalid_json())
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
            return None
        finally:
            self.request_path.unlink(missing_ok=True)

    def poll_once(self):
        if not self.request_path.exists():
            return None
        request = self._read_request()
        response = (self.handle(request) if request is not None
                    else self._reject('REQUEST_INVALID'))
        _atomic_replace(self.response_path, response)
        return response

    def _worker_main(self):
        while not self.stop_event.wait(self.poll_seconds):
            try:
                self.poll_once()
            except BaseException as error:
                with self.lock:
                    self.worker_error = error
                self.stop_event.set()
                return

    def start(self):
        with self.lock:
            if self.started or self.closed or self.thread is not None:
                raise RuntimeError('COMMAND_CHANNEL_START_REENTRY')
            self.started = True
            self.thread = Thread(target=self._worker_main,
                name='arms-paper-enable-command-' + self.run_id, daemon=True)
            self.thread.start()
            self._write_channel('LISTENING')

    def check(self):
        with self.lock:
            if self.closed:
                raise RuntimeError('COMMAND_CHANNEL_STOPPED')
            if not self.started or self.thread is None:
                raise RuntimeError('COMMAND_CHANNEL_NOT_STARTED')
            if self.worker_error is not None or not self.thread.is_alive():
                raise RuntimeError('COMMAND_CHANNEL_WORKER_FAILED') from self.worker_error

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.stop_event.set()
            thread = self.thread
        if thread is not None:
            thread.join(timeout=5.0)
            if thread.is_alive():
                raise RuntimeError('COMMAND_CHANNEL_STOP_TIMEOUT')
        self._write_channel('STOPPED')
