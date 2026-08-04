import pytest

from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)


def build_queue():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    return queue, manager


def test_enqueue_and_dequeue():

    queue, manager = build_queue()

    job = manager.create_job()

    queue.enqueue(job)

    assert len(queue) == 1

    popped = queue.dequeue()

    assert popped is job

    assert len(queue) == 0


def test_fifo_order():

    queue, manager = build_queue()

    job1 = manager.create_job()

    job2 = manager.create_job()

    queue.enqueue(job1)

    queue.enqueue(job2)

    assert queue.dequeue() is job1

    assert queue.dequeue() is job2


def test_empty_queue_returns_none():

    queue, _ = build_queue()

    assert queue.dequeue() is None


def test_reject_duplicate_job():

    queue, manager = build_queue()

    job = manager.create_job()

    queue.enqueue(job)

    with pytest.raises(
        ValueError,
    ):
        queue.enqueue(job)


def test_invalid_manager():

    with pytest.raises(
        TypeError,
    ):
        BacktestingJobQueueV2(
            job_manager=object(),
        )
