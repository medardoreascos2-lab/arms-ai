import pytest

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)


def build_queue():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    return queue, manager


def build_task(
    manager,
    *,
    output_directory="reports/test",
):

    job = manager.create_job()

    return BacktestingJobTaskV2(
        job=job,
        candles=[object()],
        output_directory=output_directory,
    )


def test_enqueue_and_dequeue():

    queue, manager = build_queue()

    task = build_task(manager)

    queue.enqueue(task)

    assert len(queue) == 1

    popped = queue.dequeue()

    assert popped is task
    assert len(queue) == 0


def test_fifo_order():

    queue, manager = build_queue()

    task1 = build_task(
        manager,
        output_directory="reports/1",
    )

    task2 = build_task(
        manager,
        output_directory="reports/2",
    )

    queue.enqueue(task1)
    queue.enqueue(task2)

    assert queue.dequeue() is task1
    assert queue.dequeue() is task2


def test_empty_queue_returns_none():

    queue, _ = build_queue()

    assert queue.dequeue() is None


def test_reject_duplicate_job():

    queue, manager = build_queue()

    task = build_task(manager)

    queue.enqueue(task)

    with pytest.raises(
        ValueError,
    ):
        queue.enqueue(task)


def test_invalid_manager():

    with pytest.raises(
        TypeError,
    ):
        BacktestingJobQueueV2(
            job_manager=object(),
        )
