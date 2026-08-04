import pytest

from backend.backtesting.backtesting_job_executor_v2 import (
    BacktestingJobExecutorV2,
)
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)
from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)


class FakeResult:

    def __init__(self):

        self.report_directory = (
            "reports/job"
        )


class FakeOrchestrator:

    def __init__(self):

        self.executed = False

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

        self.executed = True

        return FakeResult()


class FailingOrchestrator:

    def run(
        self,
        *,
        candles,
        output_directory,
    ):

        raise RuntimeError(
            "boom"
        )


def test_execute_job():

    manager = (
        BacktestingJobManagerV2()
    )

    job = manager.create_job()

    orchestrator = (
        FakeOrchestrator()
    )

    executor = (
        BacktestingJobExecutorV2(
            orchestrator=orchestrator,
        )
    )

    result = executor.execute(
        job=job,
        candles=[],
        output_directory="reports",
    )

    assert orchestrator.executed

    assert (
        job.status
        == BacktestingJobStatusV2.COMPLETED
    )

    assert (
        job.progress
        == 100.0
    )

    assert result.report_directory == (
        "reports/job"
    )


def test_failed_execution():

    manager = (
        BacktestingJobManagerV2()
    )

    job = manager.create_job()

    executor = (
        BacktestingJobExecutorV2(
            orchestrator=(
                FailingOrchestrator()
            ),
        )
    )

    with pytest.raises(
        RuntimeError,
    ):
        executor.execute(
            job=job,
            candles=[],
            output_directory="reports",
        )

    assert (
        job.status
        == BacktestingJobStatusV2.FAILED
    )

    assert (
        "boom"
        in job.error_message
    )


def test_invalid_orchestrator():

    with pytest.raises(
        TypeError,
    ):
        BacktestingJobExecutorV2(
            orchestrator=object(),
        )
