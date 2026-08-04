import pytest

from backend.backtesting.backtesting_background_worker_v2 import (
    BacktestingBackgroundWorkerV2,
)


class FakeWorker:

    def __init__(self):

        self.calls = 0

    def process_next(
        self,
    ):

        self.calls += 1

        return None


def test_invalid_worker():

    with pytest.raises(
        TypeError,
    ):
        BacktestingBackgroundWorkerV2(
            worker=object(),
        )


def test_run_single_iteration():

    fake = FakeWorker()

    background = (
        BacktestingBackgroundWorkerV2(
            worker=fake,
        )
    )

    background.run_once()

    assert fake.calls == 1
    assert background.iterations == 1
