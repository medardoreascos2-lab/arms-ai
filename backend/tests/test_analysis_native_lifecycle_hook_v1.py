"""D4D2 optional analysis-startup lifecycle hook tests.

Offline-only contract.  No NinjaTrader process, PAPER enablement or orders.
"""

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.analysis_native_startup_v1 as startup


class Lifecycle:
    def __init__(self):
        self.started = 0
        self.checked = 0
        self.closed = 0

    def start(self):
        self.started += 1

    def check(self):
        self.checked += 1

    def close(self):
        self.closed += 1


def ready_runtime():
    bootstrap = object()

    adapter = SimpleNamespace(
        status="WAITING",
        reason=None,
        activation_start=None,
        session=None,
        preactivation_session=(
            "00000000-0000-0000-"
            "0000-000000000001"
        ),
        bootstrap=bootstrap,
    )

    runtime = SimpleNamespace(
        phase="VERIFYING_WAITING",
        adapter=adapter,
        observations=[1, 2, 3],
        bootstrap=bootstrap,
    )

    return runtime


def test_run_signature_adds_only_optional_lifecycle_factory():
    signature = inspect.signature(
        startup.run
    )

    assert list(
        signature.parameters
    ) == [
        "args",
        "lifecycle_factory",
    ]

    assert (
        signature.parameters[
            "lifecycle_factory"
        ].default
        is None
    )


def test_default_none_is_strict_noop_without_reading_runtime(
    tmp_path,
):
    result = (
        startup
        ._build_optional_lifecycle(
            None,
            runtime=object(),
            run_directory=tmp_path,
            catchup_source=None,
            validate_offline=True,
        )
    )

    assert result is None


def test_factory_receives_exact_runtime_at_certified_attach_window(
    tmp_path,
):
    runtime = ready_runtime()
    lifecycle = Lifecycle()
    calls = []

    def factory(
        *,
        analysis_runtime,
        run_directory,
    ):
        calls.append(
            (
                analysis_runtime,
                run_directory,
            )
        )

        return lifecycle

    result = (
        startup
        ._build_optional_lifecycle(
            factory,
            runtime=runtime,
            run_directory=tmp_path,
            catchup_source=(
                tmp_path
                / "catchup.cs"
            ),
            validate_offline=False,
        )
    )

    assert result is lifecycle

    assert calls == [
        (
            runtime,
            tmp_path,
        )
    ]

    # Builder validates/constructs only.
    # run() owns start/check/close ordering.
    assert lifecycle.started == 0
    assert lifecycle.checked == 0
    assert lifecycle.closed == 0


@pytest.mark.parametrize(
    "mutation",
    (
        "no_catchup",
        "offline",
        "phase",
        "adapter_status",
        "adapter_reason",
        "activation",
        "session",
        "no_quarantine",
        "samples",
        "bootstrap_identity",
    ),
)
def test_factory_attach_gate_fails_closed(
    tmp_path,
    mutation,
):
    runtime = ready_runtime()

    catchup_source = (
        tmp_path
        / "catchup.cs"
    )

    validate_offline = False

    if mutation == "no_catchup":
        catchup_source = None

    elif mutation == "offline":
        validate_offline = True

    elif mutation == "phase":
        runtime.phase = "FAILED"

    elif mutation == "adapter_status":
        runtime.adapter.status = "LIVE_TAIL"

    elif mutation == "adapter_reason":
        runtime.adapter.reason = "fixture"

    elif mutation == "activation":
        runtime.adapter.activation_start = 1

    elif mutation == "session":
        runtime.adapter.session = "bound"

    elif mutation == "no_quarantine":
        runtime.adapter.preactivation_session = None

    elif mutation == "samples":
        runtime.observations = [1, 2]

    else:
        runtime.adapter.bootstrap = object()

    called = []

    with pytest.raises(
        ValueError,
        match="OPTIONAL_LIFECYCLE_ATTACH_GATE",
    ):
        startup._build_optional_lifecycle(
            lambda **kwargs: (
                called.append(kwargs)
                or Lifecycle()
            ),
            runtime=runtime,
            run_directory=tmp_path,
            catchup_source=catchup_source,
            validate_offline=validate_offline,
        )

    assert called == []


@pytest.mark.parametrize(
    "factory",
    (
        lambda **_: None,
        lambda **_: object(),
    ),
)
def test_factory_return_contract_fails_closed(
    tmp_path,
    factory,
):
    runtime = ready_runtime()

    expected = (
        "OPTIONAL_LIFECYCLE_FACTORY_RETURN"
        if factory(
            analysis_runtime=runtime,
            run_directory=tmp_path,
        )
        is None
        else "OPTIONAL_LIFECYCLE_CONTRACT"
    )

    with pytest.raises(
        ValueError,
        match=expected,
    ):
        startup._build_optional_lifecycle(
            factory,
            runtime=runtime,
            run_directory=tmp_path,
            catchup_source=(
                tmp_path
                / "catchup.cs"
            ),
            validate_offline=False,
        )


def test_run_source_places_attach_check_and_close_at_exact_seams():
    source = inspect.getsource(
        startup.run
    )

    post_catchup = source.index(
        "POST_CATCHUP_WAITING_HEALTH_SAMPLES=3"
    )

    build = source.index(
        "_build_optional_lifecycle(",
        post_catchup,
    )

    start = source.index(
        "lifecycle.start()",
        build,
    )

    finish = source.index(
        "runtime.finish_health(",
        start,
    )

    loop = source.index(
        "while runtime.phase != 'FAILED':",
        finish,
    )

    check = source.index(
        "lifecycle.check()",
        loop,
    )

    finally_block = source.index(
        "finally:",
        check,
    )

    lifecycle_close = source.index(
        "_close_optional_lifecycle(",
        finally_block,
    )

    runtime_close = source.index(
        "runtime.close()",
        lifecycle_close,
    )

    assert (
        post_catchup
        < build
        < start
        < finish
        < loop
        < check
        < finally_block
        < lifecycle_close
        < runtime_close
    )


def test_public_analysis_cli_remains_unchanged_and_hookless():
    source = Path(
        "tools/"
        "start_analysis_native_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "--start-analysis-only" in source
    assert "--validate-offline" in source

    assert "--start-current-paper" not in source
    assert "--paper-port" not in source
    assert "lifecycle_factory" not in source

    assert "run(args)" in source


def test_hook_source_has_no_paper_control_or_execution_surface():
    source = Path(
        "tools/"
        "analysis_native_startup_v1.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "service.control" not in source
    assert "CurrentPaperServiceV1" not in source
    assert "NativeCurrentPaperCoordinatorV1" not in source

    for forbidden in (
        "SubmitOrder",
        "CreateOrder(",
        "ChangeOrder",
        "CancelOrder",
        "Account.All",
        "AtmStrategy",
        "EnterLong",
        "EnterShort",
    ):
        assert forbidden not in source


class FailingCloseLifecycle(Lifecycle):
    def close(self):
        self.closed += 1

        raise RuntimeError(
            "fixture lifecycle close failure"
        )


def test_close_helper_converts_close_failure_to_value():
    lifecycle = FailingCloseLifecycle()

    error = (
        startup
        ._close_optional_lifecycle(
            lifecycle
        )
    )

    assert isinstance(
        error,
        RuntimeError,
    )

    assert str(error) == (
        "fixture lifecycle close failure"
    )

    assert lifecycle.closed == 1


def test_close_helper_none_is_noop():
    assert (
        startup
        ._close_optional_lifecycle(
            None
        )
        is None
    )


def test_run_finally_preserves_analysis_cleanup_after_lifecycle_close_failure():
    source = inspect.getsource(
        startup.run
    )

    finally_block = source.index(
        "finally:"
    )

    propagating = source.index(
        "sys.exc_info()[0]",
        finally_block,
    )

    close_lifecycle = source.index(
        "_close_optional_lifecycle(",
        propagating,
    )

    record_failure = source.index(
        "lifecycle_close_failed=True",
        close_lifecycle,
    )

    close_analysis = source.index(
        "runtime.close()",
        record_failure,
    )

    stop_server = source.index(
        "server.should_exit = True",
        close_analysis,
    )

    shutdown_result = source.index(
        "shutdown-result.json",
        stop_server,
    )

    conditional_raise = source.index(
        "and not propagating_error",
        shutdown_result,
    )

    assert (
        finally_block
        < propagating
        < close_lifecycle
        < record_failure
        < close_analysis
        < stop_server
        < shutdown_result
        < conditional_raise
    )
