from backend.api.app import create_app


def test_app_exposes_backtesting_controller():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_controller_v2",
    )


def test_controller_uses_shared_dependencies():

    app = create_app()

    controller = (
        app.state
        .backtesting_controller_v2
    )

    assert (
        controller.job_manager
        is app.state
        .backtesting_job_manager_v2
    )

    assert (
        controller.job_queue
        is app.state
        .backtesting_job_queue_v2
    )

    assert (
        controller.background_worker
        is app.state
        .backtesting_background_worker_v2
    )


def test_controller_status_is_available():

    app = create_app()

    status = (
        app.state
        .backtesting_controller_v2
        .status()
    )

    assert status == {
        "is_running": False,
        "registered_jobs": 0,
        "pending_tasks": 0,
        "iterations": 0,
        "last_error": None,
    }
