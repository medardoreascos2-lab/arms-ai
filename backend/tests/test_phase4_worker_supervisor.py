"""R42A deterministic tests for worker process supervision."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.worker_supervisor import (
    RestartPolicy,
    SupervisorLeaseError,
    SupervisorStateError,
    WorkerState,
    WorkerSupervisor,
    WorkerSupervisorConfig,
)


NOW = datetime(2026, 10, 3, 18, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class FakeProcess:
    def __init__(self, *, auto_stop=True, force_stops=True, start_error=None):
        self.auto_stop = auto_stop
        self.force_stops = force_stops
        self.start_error = start_error
        self.running = False
        self.code = None
        self.starts = 0
        self.stop_requests = 0
        self.force_stops_called = 0

    def start(self):
        self.starts += 1
        if self.start_error is not None:
            raise self.start_error
        self.running = True

    def request_stop(self):
        self.stop_requests += 1
        if self.auto_stop:
            self.running = False
            self.code = 0

    def force_stop(self):
        self.force_stops_called += 1
        if self.force_stops:
            self.running = False
            self.code = -9

    def is_running(self):
        return self.running

    def exit_code(self):
        return self.code

    def crash(self, code=1):
        self.running = False
        self.code = code


class FakeFactory:
    def __init__(self, process_options=None):
        self.options = list(process_options or [])
        self.processes = []
        self.calls = []

    def __call__(self, worker_id, generation):
        self.calls.append((worker_id, generation))
        options = self.options.pop(0) if self.options else {}
        process = FakeProcess(**options)
        self.processes.append(process)
        return process


def supervisor(clock, factory, **config):
    tokens = iter(f"lease-token-{index:04d}" for index in range(1, 20))
    return WorkerSupervisor(
        worker_id="outbox_worker",
        process_factory=factory,
        clock=clock,
        config=WorkerSupervisorConfig(**config),
        token_factory=lambda: next(tokens),
    )


def test_start_creates_running_generation_and_non_authorizing_lease():
    clock = FakeClock()
    factory = FakeFactory()
    runtime = supervisor(clock, factory)
    status = runtime.start()
    assert status.state is WorkerState.RUNNING
    assert status.generation == 1
    assert status.restart_count == 0
    assert status.lease.expires_at == NOW + timedelta(seconds=45)
    assert "lease-token-0001" not in repr(status.lease)
    assert status.lease.execution_authorized is False
    assert status.execution_authorized is False
    assert status.external_delivery_authorized is False
    assert factory.calls == [("outbox_worker", 1)]
    with pytest.raises(SupervisorStateError, match="STOPPED"):
        runtime.start()


def test_heartbeat_requires_current_unexpired_lease_and_renews_deadlines():
    clock = FakeClock()
    runtime = supervisor(clock, FakeFactory())
    started = runtime.start()
    token = started.lease.token
    clock.advance(10)
    renewed = runtime.heartbeat(token)
    assert renewed.last_heartbeat_at == NOW + timedelta(seconds=10)
    assert renewed.lease.expires_at == NOW + timedelta(seconds=55)
    with pytest.raises(SupervisorLeaseError, match="does not match"):
        runtime.heartbeat("lease-token-wrong")
    clock.advance(46)
    with pytest.raises(SupervisorLeaseError, match="expired"):
        runtime.heartbeat(token)


def test_graceful_stop_is_idempotent_and_never_restarts():
    clock = FakeClock()
    factory = FakeFactory()
    runtime = supervisor(clock, factory)
    runtime.start()
    status = runtime.stop()
    assert status.state is WorkerState.STOPPED
    assert factory.processes[0].stop_requests == 1
    assert factory.processes[0].force_stops_called == 0
    assert runtime.stop().state is WorkerState.STOPPED
    assert len(factory.processes) == 1


def test_hung_shutdown_is_forced_after_grace_period():
    clock = FakeClock()
    factory = FakeFactory(({"auto_stop": False},))
    runtime = supervisor(clock, factory, graceful_shutdown_seconds=5)
    assert runtime.start().state is WorkerState.RUNNING
    assert runtime.stop().state is WorkerState.STOPPING
    clock.advance(5)
    status = runtime.poll()
    assert status.state is WorkerState.STOPPED
    assert factory.processes[0].force_stops_called == 1


def test_crashes_restart_only_to_configured_maximum():
    clock = FakeClock()
    factory = FakeFactory()
    runtime = supervisor(
        clock,
        factory,
        restart_policy=RestartPolicy.ON_FAILURE,
        max_restart_count=2,
    )
    runtime.start()
    factory.processes[0].crash()
    assert runtime.poll().state is WorkerState.RUNNING
    assert runtime.status().restart_count == 1
    factory.processes[1].crash()
    assert runtime.poll().state is WorkerState.RUNNING
    assert runtime.status().restart_count == 2
    factory.processes[2].crash()
    exhausted = runtime.poll()
    assert exhausted.state is WorkerState.FAILED
    assert exhausted.restart_count == 2
    assert len(factory.processes) == 3
    assert exhausted.last_failure is not None
    assert exhausted.last_failure.execution_authorized is False


def test_restart_policy_distinguishes_clean_exit_from_failure():
    clock = FakeClock()
    on_failure_factory = FakeFactory()
    on_failure = supervisor(
        clock, on_failure_factory, restart_policy=RestartPolicy.ON_FAILURE
    )
    on_failure.start()
    on_failure_factory.processes[0].crash(code=0)
    assert on_failure.poll().state is WorkerState.FAILED
    assert len(on_failure_factory.processes) == 1

    always_factory = FakeFactory()
    always = supervisor(clock, always_factory, restart_policy=RestartPolicy.ALWAYS)
    always.start()
    always_factory.processes[0].crash(code=0)
    assert always.poll().state is WorkerState.RUNNING
    assert len(always_factory.processes) == 2


def test_heartbeat_timeout_uses_graceful_stop_then_restart_policy():
    clock = FakeClock()
    factory = FakeFactory()
    runtime = supervisor(
        clock,
        factory,
        heartbeat_timeout_seconds=5,
        lease_seconds=10,
        restart_policy=RestartPolicy.ON_FAILURE,
    )
    runtime.start()
    clock.advance(5)
    status = runtime.poll()
    assert status.state is WorkerState.RUNNING
    assert status.generation == 2
    assert status.restart_count == 1
    assert factory.processes[0].stop_requests == 1
    assert "heartbeat timed out" in status.last_failure.message


def test_unstoppable_process_fails_closed_without_spawning_replacement():
    clock = FakeClock()
    factory = FakeFactory(({"auto_stop": False, "force_stops": False},))
    runtime = supervisor(
        clock,
        factory,
        heartbeat_timeout_seconds=3,
        lease_seconds=5,
        graceful_shutdown_seconds=2,
    )
    runtime.start()
    clock.advance(3)
    assert runtime.poll().state is WorkerState.STOPPING
    clock.advance(2)
    failed = runtime.poll()
    assert failed.state is WorkerState.FAILED
    assert len(factory.processes) == 1
    assert failed.lease is None


def test_start_failure_is_sanitized_and_has_no_restart_loop():
    clock = FakeClock()
    factory = FakeFactory(
        ({"start_error": RuntimeError("token=fixture-supervisor-secret")},)
    )
    runtime = supervisor(clock, factory)
    failed = runtime.start()
    assert failed.state is WorkerState.FAILED
    assert "fixture-supervisor-secret" not in repr(failed)
    assert len(factory.processes) == 1
    assert runtime.poll().state is WorkerState.FAILED


@pytest.mark.parametrize(
    "changes",
    (
        {"heartbeat_timeout_seconds": 0},
        {"lease_seconds": 0},
        {"graceful_shutdown_seconds": 0},
        {"heartbeat_timeout_seconds": 10, "lease_seconds": 5},
        {"max_restart_count": -1},
    ),
)
def test_invalid_supervisor_config_is_rejected(changes):
    with pytest.raises(ValueError):
        WorkerSupervisorConfig(**changes)
