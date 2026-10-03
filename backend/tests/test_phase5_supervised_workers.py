"""R54A local supervised-worker rehearsal with no external transport."""

from datetime import datetime, timedelta, timezone

from backend.phase3 import (
    DurableOutbox,
    DurableStatePayload,
    OutboxEvent,
    OutboxStatus,
    OutboxWorker,
    Phase3DurableStateStore,
    TenantIdentity,
    WorkerConfig,
    WorkerStepStatus,
)
from backend.phase4.retry_operations import DurableRetryOperations, RetryOperationsPolicy
from backend.phase4.worker_supervisor import (
    RestartPolicy,
    WorkerState,
    WorkerSupervisor,
    WorkerSupervisorConfig,
)


NOW = datetime(2026, 10, 4, 1, 0, tzinfo=timezone.utc)


class LocalClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class LocalWorkerProcess:
    def __init__(self):
        self.running = False
        self.code = None
        self.start_calls = 0
        self.stop_requests = 0
        self.force_stop_calls = 0

    def start(self):
        self.start_calls += 1
        self.running = True

    def request_stop(self):
        self.stop_requests += 1
        self.running = False
        self.code = 0

    def force_stop(self):
        self.force_stop_calls += 1
        self.running = False
        self.code = -9

    def is_running(self):
        return self.running

    def exit_code(self):
        return self.code

    def crash(self):
        self.running = False
        self.code = 1


class LocalProcessFactory:
    def __init__(self):
        self.processes = []
        self.calls = []

    def __call__(self, worker_id, generation):
        self.calls.append((worker_id, generation))
        process = LocalWorkerProcess()
        self.processes.append(process)
        return process


def _supervisor(clock, factory, *, maximum_restarts=2):
    tokens = iter(f"phase5-worker-lease-{index:04d}" for index in range(1, 20))
    return WorkerSupervisor(
        worker_id="phase5_outbox_worker",
        process_factory=factory,
        clock=clock,
        config=WorkerSupervisorConfig(
            heartbeat_timeout_seconds=5,
            lease_seconds=10,
            graceful_shutdown_seconds=2,
            restart_policy=RestartPolicy.ON_FAILURE,
            max_restart_count=maximum_restarts,
        ),
        token_factory=lambda: next(tokens),
    )


def test_local_supervisor_start_heartbeat_lease_crash_restart_and_clean_shutdown():
    clock = LocalClock()
    factory = LocalProcessFactory()
    supervisor = _supervisor(clock, factory)

    started = supervisor.start()
    first_token = started.lease.token
    assert started.state is WorkerState.RUNNING
    assert started.generation == 1
    assert started.lease.expires_at == NOW + timedelta(seconds=10)
    assert first_token not in repr(started.lease)
    assert started.execution_authorized is False
    assert started.external_delivery_authorized is False

    clock.advance(3)
    heartbeat = supervisor.heartbeat(first_token)
    assert heartbeat.last_heartbeat_at == NOW + timedelta(seconds=3)
    assert heartbeat.lease.expires_at == NOW + timedelta(seconds=13)

    factory.processes[0].crash()
    restarted = supervisor.poll()
    assert restarted.state is WorkerState.RUNNING
    assert restarted.generation == 2
    assert restarted.restart_count == 1
    assert restarted.lease.token != first_token
    assert factory.calls == [
        ("phase5_outbox_worker", 1),
        ("phase5_outbox_worker", 2),
    ]

    stopped = supervisor.stop()
    assert stopped.state is WorkerState.STOPPED
    assert stopped.lease is None
    assert factory.processes[1].stop_requests == 1
    assert factory.processes[1].force_stop_calls == 0
    assert supervisor.stop().state is WorkerState.STOPPED
    assert len(factory.processes) == 2


def test_local_supervisor_stops_restarting_at_configured_maximum():
    clock = LocalClock()
    factory = LocalProcessFactory()
    supervisor = _supervisor(clock, factory, maximum_restarts=2)
    supervisor.start()

    for expected_restart in (1, 2):
        factory.processes[-1].crash()
        status = supervisor.poll()
        assert status.state is WorkerState.RUNNING
        assert status.restart_count == expected_restart

    factory.processes[-1].crash()
    exhausted = supervisor.poll()
    assert exhausted.state is WorkerState.FAILED
    assert exhausted.restart_count == 2
    assert exhausted.lease is None
    assert len(factory.processes) == 3
    assert exhausted.last_failure is not None
    assert exhausted.last_failure.execution_authorized is False
    assert exhausted.external_delivery_authorized is False


def test_supervised_outbox_reaches_dead_letter_at_max_attempts_without_delivery(
    tmp_path,
):
    clock = LocalClock()
    factory = LocalProcessFactory()
    supervisor = _supervisor(clock, factory)
    supervisor.start()
    local_attempts = []

    event = OutboxEvent(
        tenant=TenantIdentity("tenant-a"),
        event_kind="SYNTHETIC_NOTIFICATION",
        dedupe_key="phase5:r54a:dead-letter",
        payload=DurableStatePayload((
            ("destination", "local-test-receiver"),
            ("simulated", True),
        )),
        created_at=NOW,
        available_at=NOW,
    )
    path = tmp_path / "phase5-r54a.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        DurableOutbox(store).enqueue(event)

        def local_failure(item):
            local_attempts.append(item.event_id)
            raise RuntimeError("token=synthetic-r54a-local-failure")

        worker = OutboxWorker(
            store,
            tenant_id="tenant-a",
            worker_id="phase5_outbox_worker",
            clock=clock,
            transport=local_failure,
            config=WorkerConfig(
                lease_seconds=10,
                max_attempts=2,
                initial_backoff_seconds=1,
                maximum_backoff_seconds=1,
            ),
            token_factory=lambda: "phase5-outbox-claim-token-0001",
        )

        first = worker.process_one()
        assert first.status is WorkerStepStatus.RETRY_SCHEDULED
        assert first.record.status is OutboxStatus.PENDING
        assert first.record.attempt_count == 1
        assert "synthetic-r54a-local-failure" not in first.record.last_error

        clock.advance(1)
        supervisor.heartbeat(supervisor.status().lease.token)
        second = worker.process_one()
        assert second.status is WorkerStepStatus.DEAD_LETTERED
        assert second.record.status is OutboxStatus.DEAD_LETTER
        assert second.record.attempt_count == 2
        assert second.execution_authorized is False
        assert second.external_delivery_authorized is False

        inspected = DurableRetryOperations(
            store,
            RetryOperationsPolicy(maximum_attempts=2),
        ).inspect_dead_letters(tenant_id="tenant-a")
        assert len(inspected) == 1
        assert inspected[0].event_id == event.event_id
        assert inspected[0].retry_eligible is False
        assert inspected[0].blocking_reasons == ("MAX_ATTEMPTS_REACHED",)
        assert inspected[0].external_delivery_authorized is False

        worker.request_shutdown()
        assert worker.process_one().status is WorkerStepStatus.SHUTDOWN
        assert worker.execution_authorized is False
        assert worker.external_delivery_authorized is False

    stopped = supervisor.stop()
    assert stopped.state is WorkerState.STOPPED
    assert local_attempts == [event.event_id, event.event_id]
    assert len(factory.processes) == 1
