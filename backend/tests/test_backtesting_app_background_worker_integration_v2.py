from backend.api.app import create_app


def test_app_exposes_background_worker():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_background_worker_v2",
    )


def test_background_worker_uses_shared_worker():

    app = create_app()

    background = (
        app.state
        .backtesting_background_worker_v2
    )

    assert (
        background.worker
        is app.state
        .backtesting_worker_v2
    )
