import pytest

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
)


def test_create_job():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    assert job.job_id

    assert (
        job.status
        == BacktestingJobStatusV2.PENDING
    )

    assert (
        manager.get_job(job.job_id)
        is job
    )


def test_list_jobs():

    manager = BacktestingJobManagerV2()

    manager.create_job()
    manager.create_job()

    jobs = manager.list_jobs()

    assert len(jobs) == 2


def test_delete_job():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    manager.delete_job(job.job_id)

    assert (
        manager.get_job(job.job_id)
        is None
    )


def test_unknown_job_returns_none():

    manager = BacktestingJobManagerV2()

    assert (
        manager.get_job("unknown")
        is None
    )


def test_duplicate_job_registration():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    with pytest.raises(
        ValueError,
    ):
        manager.register_job(job)
