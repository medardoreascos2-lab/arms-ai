import pytest

from backend.pipeline.pipeline_mode import PipelineMode


def test_pipeline_mode_contains_expected_values():
    assert PipelineMode.SIMULATION.value == "SIMULATION"
    assert PipelineMode.BACKTEST.value == "BACKTEST"
    assert PipelineMode.PAPER.value == "PAPER"
    assert PipelineMode.LIVE.value == "LIVE"


def test_pipeline_mode_can_be_created_from_string():
    assert PipelineMode("SIMULATION") is PipelineMode.SIMULATION
    assert PipelineMode("BACKTEST") is PipelineMode.BACKTEST


def test_pipeline_mode_rejects_unknown_value():
    with pytest.raises(ValueError):
        PipelineMode("UNKNOWN")
