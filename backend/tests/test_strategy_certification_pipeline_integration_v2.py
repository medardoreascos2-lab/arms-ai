from backend.api.app import create_app


def test_strategy_certification_pipeline_registers_certified_strategy():

    app = create_app()

    registry = (
        app.state
        .strategy_registry_v2
    )

    pipeline = (
        app.state
        .strategy_certification_pipeline_v2
    )


    result = pipeline.run()


    assert result is not None


    strategies = (
        registry.list()
    )


    assert len(
        strategies
    ) >= 1


    assert strategies[0][
        "status"
    ] == "CERTIFIED"
