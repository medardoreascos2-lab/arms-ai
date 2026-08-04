import pytest

from backend.backtesting.backtesting_job_manager_v2 import (
    BacktestingJobManagerV2,
)
from backend.backtesting.backtesting_job_task_v2 import (
    BacktestingJobTaskV2,
)


def test_create_job_task():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    candles = [
        object(),
        object(),
    ]

    task = BacktestingJobTaskV2(
        job=job,
        candles=candles,
        output_directory=(
            "reports/backtesting/job-001"
        ),
    )

    assert task.job is job

    assert task.candles == candles

    assert (
        task.output_directory
        == "reports/backtesting/job-001"
    )

    assert task.candle_count == 2


def test_candles_are_copied():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    candles = [
        object(),
    ]

    task = BacktestingJobTaskV2(
        job=job,
        candles=candles,
        output_directory="reports/test",
    )

    candles.append(
        object()
    )

    assert task.candle_count == 1


def test_rejects_invalid_job():

    with pytest.raises(
        TypeError,
        match="job",
    ):
        BacktestingJobTaskV2(
            job=object(),
            candles=[object()],
            output_directory="reports/test",
        )


def test_rejects_empty_candles():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    with pytest.raises(
        ValueError,
        match="candles",
    ):
        BacktestingJobTaskV2(
            job=job,
            candles=[],
            output_directory="reports/test",
        )


def test_rejects_empty_output_directory():

    manager = BacktestingJobManagerV2()

    job = manager.create_job()

    with pytest.raises(
        ValueError,
        match="output_directory",
    ):
        BacktestingJobTaskV2(
            job=job,
            candles=[object()],
            output_directory="",
        )


def test_to_dict():

    manager = BacktestingJobManagerV2()

    job = manager.create_job(
        job_id="job-001",
    )

    task = BacktestingJobTaskV2(
        job=job,
        candles=[
            object(),
            object(),
        ],
        output_directory="reports/job-001",
    )

    payload = task.to_dict()

    assert payload == {
        "job_id": "job-001",
        "candle_count": 2,
        "output_directory": (
            "reports/job-001"
        ),
    }
