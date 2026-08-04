from threading import Event
from time import monotonic, sleep

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


class SignalingWorker:

    def __init__(
        self,
    ):

        self.calls = 0
        self.called = Event()

    def process_next(
        self,
    ):

        self.calls += 1
        self.called.set()

        return None


def wait_until(
    predicate,
    *,
    timeout=1.0,
):

    deadline = (
        monotonic()
        + timeout
    )

    while monotonic() < deadline:

        if predicate():
            return True

        sleep(0.01)

    return False


def test_default_state_is_stopped():

    background = (
        BacktestingBackgroundWorkerV2(
            worker=FakeWorker(),
        )
    )

    assert (
        background.is_running
        is False
    )


def test_rejects_invalid_poll_interval():

    with pytest.raises(
        ValueError,
        match="poll_interval",
    ):
        BacktestingBackgroundWorkerV2(
            worker=FakeWorker(),
            poll_interval=0,
        )


def test_start_and_stop():

    worker = SignalingWorker()

    background = (
        BacktestingBackgroundWorkerV2(
            worker=worker,
            poll_interval=0.01,
        )
    )

    background.start()

    assert (
        background.is_running
        is True
    )

    assert worker.called.wait(
        timeout=1.0,
    )

    background.stop(
        timeout=1.0,
    )

    assert (
        background.is_running
        is False
    )


def test_start_is_idempotent():

    background = (
        BacktestingBackgroundWorkerV2(
            worker=FakeWorker(),
            poll_interval=0.01,
        )
    )

    first_thread = (
        background.start()
    )

    second_thread = (
        background.start()
    )

    assert (
        second_thread
        is first_thread
    )

    background.stop(
        timeout=1.0,
    )


def test_continuous_processing():

    worker = FakeWorker()

    background = (
        BacktestingBackgroundWorkerV2(
            worker=worker,
            poll_interval=0.01,
        )
    )

    background.start()

    assert wait_until(
        lambda: worker.calls >= 2,
        timeout=1.0,
    )

    background.stop(
        timeout=1.0,
    )

    assert worker.calls >= 2


def test_stop_before_start_is_safe():

    background = (
        BacktestingBackgroundWorkerV2(
            worker=FakeWorker(),
        )
    )

    background.stop(
        timeout=0.1,
    )

    assert (
        background.is_running
        is False
    )


def test_context_manager_lifecycle():

    worker = SignalingWorker()

    with BacktestingBackgroundWorkerV2(
        worker=worker,
        poll_interval=0.01,
    ) as background:

        assert (
            background.is_running
            is True
        )

        assert worker.called.wait(
            timeout=1.0,
        )

    assert (
        background.is_running
        is False
    )
