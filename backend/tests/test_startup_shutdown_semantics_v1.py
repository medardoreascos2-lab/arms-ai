"""Operator interruption semantics for the analysis-only startup harness."""
import ast
from pathlib import Path


ORCHESTRATOR = Path(
    "tools/analysis_native_startup_v1.py"
)

STATE_MACHINE = Path(
    "backend/market_data/analysis_startup_v1.py"
)


def function(path, name):
    text = path.read_text(
        encoding="utf-8"
    )
    tree = ast.parse(text)

    node = next(
        item
        for item in tree.body
        if (
            isinstance(item, ast.FunctionDef)
            and item.name == name
        )
    )

    return text, node


def startup_try():
    text, run = function(
        ORCHESTRATOR,
        "run",
    )

    tries = [
        node
        for node in ast.walk(run)
        if isinstance(node, ast.Try)
    ]

    assert len(tries) == 1

    return text, tries[0]


def handler_name(handler):
    assert handler.type is not None
    return ast.unparse(
        handler.type
    )


def test_keyboard_interrupt_has_dedicated_handler_before_fail_closed_fallback():
    text, node = startup_try()

    assert [
        handler_name(handler)
        for handler in node.handlers
    ] == [
        "KeyboardInterrupt",
        "BaseException",
    ]

    source = ast.get_source_segment(
        text,
        node.handlers[0],
    )

    assert (
        "status='STOPPED'"
        in source
    )

    assert (
        "shutdown_reason='OPERATOR_INTERRUPT'"
        in source
    )

    assert (
        "interruption_type=type(error).__name__"
        in source
    )

    assert (
        "pre_shutdown_health=runtime.health()"
        in source
    )

    assert (
        "runtime.revoke("
        not in source
    )

    assert isinstance(
        node.handlers[0].body[-1],
        ast.Raise,
    )


def test_non_keyboard_base_exception_remains_fail_closed():
    text, node = startup_try()

    fallback = ast.get_source_segment(
        text,
        node.handlers[1],
    )

    assert (
        "runtime.revoke('STARTUP_OR_HEALTH_FAILED')"
        in fallback
    )

    assert (
        "status='FAILED'"
        in fallback
    )

    assert (
        "error_type=type(error).__name__"
        in fallback
    )

    assert isinstance(
        node.handlers[1].body[-1],
        ast.Raise,
    )


def test_finally_still_closes_runtime_and_persists_shutdown_result():
    text, node = startup_try()

    first = node.finalbody[0].lineno
    last = node.finalbody[-1].end_lineno

    source = "\n".join(
        text.splitlines()[
            first - 1:last
        ]
    )

    assert (
        source.index(
            "runtime.close()"
        )
        < source.index(
            "shutdown-result.json"
        )
    )

    assert (
        "owned_frontend_stopped="
        in source
    )

    assert (
        "owned_backend_stopped="
        in source
    )
    assert (
        source.index("pre_cleanup_health = runtime.health()")
        < source.index("runtime.close()")
        < source.index("_shutdown_fault_telemetry(pre_cleanup_health)")
    )


def test_state_machine_close_preserves_startup_shutdown_reason():
    text = STATE_MACHINE.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(text)

    cls = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name
            == "AnalysisStartupV1"
        )
    )

    close = next(
        node
        for node in cls.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "close"
        )
    )

    source = ast.get_source_segment(
        text,
        close,
    )

    assert (
        "self.revoke('STARTUP_SHUTDOWN')"
        in source
    )
