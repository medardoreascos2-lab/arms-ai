import pytest

from backend.backtesting.backtesting_controller_v2 import (
    BacktestingControllerV2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)


class FakeBackgroundWorker:

    def __init__(self):

        self.start_calls = 0
        self.stop_calls = 0
        self.is_running = False
        self.iterations = 0
        self.last_error = None

    def start(self):

        self.start_calls += 1
        self.is_running = True

        return object()

    def stop(
        self,
        *,
        timeout=None,
    ):

        self.stop_calls += 1
        self.is_running = False


def build_controller():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    background_worker = (
        FakeBackgroundWorker()
    )

    controller = BacktestingControllerV2(
        job_manager=manager,
        job_queue=queue,
        background_worker=background_worker,
    )

    return (
        controller,
        manager,
        queue,
        background_worker,
    )


def test_create_controller():

    (
        controller,
        manager,
        queue,
        background_worker,
    ) = build_controller()

    assert controller.job_manager is manager
    assert controller.job_queue is queue

    assert (
        controller.background_worker
        is background_worker
    )


def test_start_and_stop():

    (
        controller,
        _,
        _,
        background_worker,
    ) = build_controller()

    controller.start()

    assert background_worker.start_calls == 1
    assert controller.is_running is True

    controller.stop(
        timeout=1.0,
    )

    assert background_worker.stop_calls == 1
    assert controller.is_running is False


def test_status():

    (
        controller,
        manager,
        queue,
        _,
    ) = build_controller()

    manager.create_job()

    status = controller.status()

    assert status == {
        "is_running": False,
        "registered_jobs": 1,
        "pending_tasks": 0,
        "iterations": 0,
        "last_error": None,
    }


def test_rejects_invalid_job_manager():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    with pytest.raises(
        TypeError,
        match="job_manager",
    ):
        BacktestingControllerV2(
            job_manager=object(),
            job_queue=queue,
            background_worker=(
                FakeBackgroundWorker()
            ),
        )


def test_rejects_queue_with_different_manager():

    manager_a = BacktestingJobManagerV2()
    manager_b = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager_b,
    )

    with pytest.raises(
        ValueError,
        match="job_manager",
    ):
        BacktestingControllerV2(
            job_manager=manager_a,
            job_queue=queue,
            background_worker=(
                FakeBackgroundWorker()
            ),
        )


def test_rejects_invalid_background_worker():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    with pytest.raises(
        TypeError,
        match="background_worker",
    ):
        BacktestingControllerV2(
            job_manager=manager,
            job_queue=queue,
            background_worker=object(),
        )
