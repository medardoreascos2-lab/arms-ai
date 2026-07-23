import pytest

from backend.api.app import create_app
from backend.execution.execution_decision_engine import (
    ExecutionDecisionEngine,
)


def test_create_app_builds_default_execution_decision_engine():
    app = create_app()

    engine = (
        app.state.execution_decision_engine
    )

    assert isinstance(
        engine,
        ExecutionDecisionEngine,
    )

    assert engine.minimum_confidence == 0.70


def test_create_app_accepts_custom_execution_decision_engine():
    engine = ExecutionDecisionEngine(
        minimum_confidence=0.85,
    )

    app = create_app(
        execution_decision_engine=engine
    )

    assert (
        app.state.execution_decision_engine
        is engine
    )


def test_create_app_rejects_invalid_execution_decision_engine():
    with pytest.raises(
        TypeError,
        match="execution_decision_engine",
    ):
        create_app(
            execution_decision_engine=object()
        )
