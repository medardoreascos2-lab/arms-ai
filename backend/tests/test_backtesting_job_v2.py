from datetime import datetime
import pytest

from backend.backtesting.backtesting_job_v2 import (
    BacktestingJobStatusV2,
    BacktestingJobV2,
)


def test_create_job():

    job = BacktestingJobV2(
        job_id="job-001",
    )

    assert job.job_id == "job-001"

    assert (
        job.status
        == BacktestingJobStatusV2.PENDING
    )

    assert job.progress == 0.0

    assert isinstance(
        job.created_at,
        datetime,
    )

    assert job.started_at is None
    assert job.finished_at is None
    assert job.error_message is None
    assert job.report_directory is None


def test_progress_validation():

    job = BacktestingJobV2(
        job_id="job-001",
    )

    job.progress = 45.5

    assert job.progress == 45.5

    with pytest.raises(ValueError):
        job.progress = -1

    with pytest.raises(ValueError):
        job.progress = 101


def test_status_transition():

    job = BacktestingJobV2(
        job_id="job-001",
    )

    job.start()

    assert (
        job.status
        == BacktestingJobStatusV2.RUNNING
    )

    assert job.started_at is not None

    job.finish(
        report_directory="reports/job-001",
    )

    assert (
        job.status
        == BacktestingJobStatusV2.COMPLETED
    )

    assert job.finished_at is not None

    assert (
        job.report_directory
        == "reports/job-001"
    )


def test_fail_job():

    job = BacktestingJobV2(
        job_id="job-001",
    )

    job.fail(
        "Unexpected error"
    )

    assert (
        job.status
        == BacktestingJobStatusV2.FAILED
    )

    assert (
        job.error_message
        == "Unexpected error"
    )


def test_to_dict():

    job = BacktestingJobV2(
        job_id="job-001",
    )

    payload = job.to_dict()

    assert payload["job_id"] == "job-001"

    assert payload["status"] == "PENDING"

    assert payload["progress"] == 0.0
