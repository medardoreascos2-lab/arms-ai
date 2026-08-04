import pytest

from backend.backtesting.backtesting_worker_v2 import (
    BacktestingWorkerV2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_queue_v2 import (
    BacktestingJobQueueV2,
)
from backend.backtesting.backtesting_job_executor_v2 import (
    BacktestingJobExecutorV2,
)


class FakeExecutor:

    def __init__(self):

        self.executed_jobs = []

    def execute(
        self,
        *,
        job,
        candles,
        output_directory,
    ):

        self.executed_jobs.append(job)

        return object()


def build_worker():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    executor = FakeExecutor()

    worker = BacktestingWorkerV2(
        queue=queue,
        executor=executor,
    )

    return (
        worker,
        manager,
        queue,
        executor,
    )


def test_process_single_job():

    (
        worker,
        manager,
        queue,
        executor,
    ) = build_worker()

    job = manager.create_job()

    queue.enqueue(job)

    processed = worker.process_next(
        candles=[],
        output_directory="reports",
    )

    assert processed is job

    assert executor.executed_jobs == [job]

    assert len(queue) == 0


def test_process_empty_queue():

    (
        worker,
        *_,
    ) = build_worker()

    assert (
        worker.process_next(
            candles=[],
            output_directory="reports",
        )
        is None
    )


def test_invalid_executor():

    manager = BacktestingJobManagerV2()

    queue = BacktestingJobQueueV2(
        job_manager=manager,
    )

    with pytest.raises(
        TypeError,
    ):
        BacktestingWorkerV2(
            queue=queue,
            executor=object(),
        )
