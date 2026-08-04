from backend.api.app import create_app


def test_app_exposes_executor_and_worker():

    app = create_app()

    assert hasattr(
        app.state,
        "backtesting_job_executor_v2",
    )

    assert hasattr(
        app.state,
        "backtesting_worker_v2",
    )


def test_worker_uses_shared_dependencies():

    app = create_app()

    worker = (
        app.state.backtesting_worker_v2
    )

    executor = (
        app.state.backtesting_job_executor_v2
    )

    assert (
        worker.executor
        is executor
    )

    assert (
        worker.queue
        is app.state.backtesting_job_queue_v2
    )

    assert (
        executor.orchestrator
        is app.state.backtesting_orchestrator_v2
    )
