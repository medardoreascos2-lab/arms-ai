from backend.api.app import create_app


def test_strategy_certification_pipeline_respects_certification_status():

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
    assert result.certification is not None

    status = (
        result.certification.status
    )

    strategies = (
        registry.list()
    )

    if status == "CERTIFIED":

        assert len(
            strategies
        ) >= 1

        assert strategies[0][
            "status"
        ] == "CERTIFIED"

    else:

        assert status in {
            "PROVISIONAL",
            "REJECTED",
        }

        assert strategies == []
