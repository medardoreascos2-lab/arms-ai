import pytest

from backend.api.app import create_app


def test_strategy_certification_entrypoint_fails_closed_on_insufficient_fixed_dataset():

    app = create_app()

    registry = (
        app.state
        .strategy_registry_v2
    )

    pipeline = (
        app.state
        .strategy_certification_pipeline_v2
    )

    with pytest.raises(
        ValueError,
        match="trade_pnls no puede estar vacío",
    ):
        pipeline.run()

    assert registry.list() == []
