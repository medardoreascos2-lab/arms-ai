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


def build_task(manager):

    job = manager.create_job()

    return BacktestingJobTaskV2(
        job=job,
        candles=[object()],
        output_directory="reports/job",
    )


def test_enqueue_task():

    queue, manager = build_queue()

    task = build_task(manager)

    queue.enqueue(task)

    assert len(queue) == 1

    popped = queue.dequeue()

    assert popped is task


def test_reject_old_job_object():

    queue, manager = build_queue()

    job = manager.create_job()

    with pytest.raises(
        TypeError,
        match="BacktestingJobTaskV2",
    ):
        queue.enqueue(job)
