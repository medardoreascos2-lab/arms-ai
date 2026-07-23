import pytest

from backend.api.app import create_app
from backend.risk_management.position_sizing_engine import (
    PositionSizingEngine,
)


def test_create_app_builds_default_position_sizing_engine():
    app = create_app()

    engine = app.state.position_sizing_engine

    assert isinstance(
        engine,
        PositionSizingEngine,
    )

    assert engine.minimum_contracts == 1
    assert engine.maximum_contracts == 20


def test_create_app_accepts_custom_position_sizing_engine():
    engine = PositionSizingEngine(
        minimum_contracts=1,
        maximum_contracts=5,
    )

    app = create_app(
        position_sizing_engine=engine
    )

    assert (
        app.state.position_sizing_engine
        is engine
    )


def test_create_app_rejects_invalid_position_sizing_engine():
    with pytest.raises(
        TypeError,
        match="position_sizing_engine",
    ):
        create_app(
            position_sizing_engine=object()
        )
