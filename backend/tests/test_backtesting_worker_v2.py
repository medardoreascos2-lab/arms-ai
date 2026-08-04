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
from backend.backtesting.backtesting_worker_v2 import (
    BacktestingWorkerV2,
)


class FakeExecutor:

    def __init__(self):

        self.calls = []

    def execute(
        self,
        *,
        job,
        candles,
        output_directory,
    ):

        self.calls.append(
            {
                "job": job,
                "candles": candles,
                "output_directory": (
                    output_directory
                ),
            }
        )

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

    candles = [
        object(),
    ]

    task = BacktestingJobTaskV2(
        job=job,
        candles=candles,
        output_directory="reports/job",
    )

    queue.enqueue(task)

    processed = worker.process_next()

    assert processed is job
    assert len(queue) == 0

    assert executor.calls == [
        {
            "job": job,
            "candles": task.candles,
            "output_directory": (
                "reports/job"
            ),
        },
    ]


def test_process_empty_queue():

    worker, *_ = build_worker()

    assert worker.process_next() is None


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
