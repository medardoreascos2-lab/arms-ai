from fastapi.testclient import TestClient

from backend.api.app import create_app


class FakeBackgroundWorker:

    def __init__(self):

        self.start_calls = 0
        self.stop_calls = 0
        self.is_running = False

    def start(self):

        self.start_calls += 1
        self.is_running = True

        return object()

    def stop(
        self,
        *,
        timeout=None,
    ):

        self.stop_calls += 1
        self.is_running = False


def test_lifespan_starts_and_stops_background_worker():

    background_worker = (
        FakeBackgroundWorker()
    )

    app = create_app(
        backtesting_background_worker_v2=(
            background_worker
        ),
        start_backtesting_background_worker=True,
    )

    assert background_worker.start_calls == 0

    with TestClient(app) as client:

        response = client.get(
            "/openapi.json"
        )

        assert response.status_code == 200

        assert (
            background_worker.start_calls
            == 1
        )

        assert (
            background_worker.is_running
            is True
        )

    assert background_worker.stop_calls == 1

    assert (
        background_worker.is_running
        is False
    )


def test_lifespan_can_disable_background_worker():

    background_worker = (
        FakeBackgroundWorker()
    )

    app = create_app(
        backtesting_background_worker_v2=(
            background_worker
        ),
        start_backtesting_background_worker=False,
    )

    with TestClient(app) as client:

        response = client.get(
            "/openapi.json"
        )

        assert response.status_code == 200

    assert background_worker.start_calls == 0
    assert background_worker.stop_calls == 0


def test_background_worker_autostart_defaults_to_false():

    background_worker = (
        FakeBackgroundWorker()
    )

    app = create_app(
        backtesting_background_worker_v2=(
            background_worker
        ),
    )

    with TestClient(app):

        pass

    assert background_worker.start_calls == 0
    assert background_worker.stop_calls == 0
