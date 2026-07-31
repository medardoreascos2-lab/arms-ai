import pytest

from backend.api.app import create_app
from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
    build_runtime_context,
)


def test_create_app_accepts_runtime_context_v2():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    assert (
        app.state.runtime_context_v2
        is context
    )


def test_create_app_uses_context_trade_lifecycle_service():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    assert (
        app.state.trade_lifecycle_service_v2
        is context.trade_lifecycle_service
    )


def test_create_app_uses_context_execution_manager():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    assert (
        app.state.execution_manager_v2
        is context.execution_manager
    )

    assert (
        app.state
        .trade_lifecycle_service_v2
        .execution_manager
        is context.execution_manager
    )


def test_create_app_uses_context_position_manager():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    assert (
        app.state
        .trade_lifecycle_service_v2
        .position_manager
        is context.position_manager
    )


def test_create_app_uses_context_paper_execution_engine():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    assert (
        app.state.paper_execution_engine_v2
        is context.paper_execution_engine
    )


def test_create_app_preserves_context_portfolio_dependencies():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
    )

    lifecycle = (
        context.trade_lifecycle_service
    )

    assert (
        app.state.portfolio_manager_v2
        is lifecycle.portfolio_manager_v2
    )

    assert (
        app.state.trade_journal_v2
        is lifecycle.trade_journal_v2
    )


def test_create_app_without_context_preserves_old_behavior():
    app = create_app()

    assert (
        app.state.runtime_context_v2
        is None
    )

    assert (
        app.state.trade_lifecycle_service_v2
        is not None
    )

    assert (
        app.state.execution_manager_v2
        is not None
    )

    assert (
        app.state.paper_execution_engine_v2
        is not None
    )


def test_create_app_rejects_invalid_runtime_context():
    with pytest.raises(
        TypeError,
        match="runtime_context",
    ):
        create_app(
            runtime_context=object(),
        )


def test_create_app_rejects_conflicting_lifecycle_service():
    first_context = build_runtime_context()
    second_context = build_runtime_context()

    with pytest.raises(
        ValueError,
        match="entra en conflicto",
    ):
        create_app(
            runtime_context=first_context,
            trade_lifecycle_service_v2=(
                second_context
                .trade_lifecycle_service
            ),
        )


def test_create_app_accepts_matching_lifecycle_service():
    context = build_runtime_context()

    app = create_app(
        runtime_context=context,
        trade_lifecycle_service_v2=(
            context.trade_lifecycle_service
        ),
    )

    assert (
        app.state.trade_lifecycle_service_v2
        is context.trade_lifecycle_service
    )


def test_runtime_context_type_is_dataclass_instance():
    context = build_runtime_context()

    assert isinstance(
        context,
        RuntimeContextV2,
    )
