from backend.pipeline.arms_pipeline import ArmsPipeline


class DummyStage:
    def __init__(self):
        self.executed = False

    def run(self, context):
        self.executed = True
        context["dummy"] = "ok"
        return context


def test_pipeline_runs_registered_stage():
    stage = DummyStage()
    pipeline = ArmsPipeline(stages=[stage])

    result = pipeline.run(initial_context={"start": True})

    assert stage.executed is True
    assert result["start"] is True
    assert result["dummy"] == "ok"


def test_pipeline_runs_stages_in_order():
    execution_order = []

    class FirstStage:
        def run(self, context):
            execution_order.append("first")
            context["value"] = 1
            return context

    class SecondStage:
        def run(self, context):
            execution_order.append("second")
            context["value"] += 1
            return context

    pipeline = ArmsPipeline(
        stages=[
            FirstStage(),
            SecondStage(),
        ]
    )

    result = pipeline.run(initial_context={})

    assert execution_order == ["first", "second"]
    assert result["value"] == 2
