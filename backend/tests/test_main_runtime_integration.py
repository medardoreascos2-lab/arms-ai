from __future__ import annotations

from typing import Any

import pytest

import backend.main as main_module


class FakeLifecycleManager:
    def __init__(self) -> None:
        self.start_calls = 0
        self.shutdown_paths: list[str] = []

    def start_clean(
        self,
    ) -> dict[str, object]:
        self.start_calls += 1

        return {
            "success": True,
            "status": "RUNNING",
        }

    def shutdown_to(
        self,
        *,
        file_path: str,
    ) -> dict[str, object]:
        self.shutdown_paths.append(
            file_path
        )

        return {
            "success": True,
            "status": "STOPPED",
        }


class FakeRuntimeContext:
    def __init__(
        self,
        lifecycle_manager: FakeLifecycleManager,
    ) -> None:
        self.runtime_lifecycle_manager = (
            lifecycle_manager
        )


class FakeArmsCore:
    started = False

    def start(
        self,
    ) -> None:
        type(self).started = True


class FakeMarketConnector:
    connected = False

    def connect(
        self,
    ) -> None:
        type(self).connected = True


class FakeDataCollector:
    def __init__(
        self,
        *,
        provider: str,
    ) -> None:
        self.provider = provider


class FakeStage:
    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.kwargs = kwargs


class FakePipeline:
    should_fail = False
    received_stages: list[object] | None = None
    received_context: dict[str, object] | None = None

    def __init__(
        self,
        *,
        stages: list[object],
    ) -> None:
        type(self).received_stages = stages

    def run(
        self,
        *,
        initial_context: dict[str, object],
    ) -> None:
        type(self).received_context = initial_context

        if type(self).should_fail:
            raise RuntimeError(
                "pipeline failure"
            )


def configure_fakes(
    monkeypatch: pytest.MonkeyPatch,
    lifecycle_manager: FakeLifecycleManager,
) -> None:
    FakeArmsCore.started = False
    FakeMarketConnector.connected = False
    FakePipeline.should_fail = False
    FakePipeline.received_stages = None
    FakePipeline.received_context = None

    runtime_context = FakeRuntimeContext(
        lifecycle_manager
    )

    monkeypatch.setattr(
        main_module,
        "build_runtime_context",
        lambda *, settings: runtime_context,
    )
    monkeypatch.setattr(
        main_module,
        "ArmsCore",
        FakeArmsCore,
    )
    monkeypatch.setattr(
        main_module,
        "MarketConnector",
        FakeMarketConnector,
    )
    monkeypatch.setattr(
        main_module,
        "DataCollector",
        FakeDataCollector,
    )
    monkeypatch.setattr(
        main_module,
        "ArmsPipeline",
        FakePipeline,
    )

    stage_names = (
        "MarketStage",
        "IndicatorStage",
        "SmartMoneyStage",
        "IntelligenceStage",
        "RiskStage",
        "DecisionStage",
        "TradePlanStage",
        "ExecutionStage",
        "ReportingStage",
    )

    for stage_name in stage_names:
        monkeypatch.setattr(
            main_module,
            stage_name,
            FakeStage,
        )


def test_main_starts_and_stops_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle_manager = FakeLifecycleManager()

    configure_fakes(
        monkeypatch,
        lifecycle_manager,
    )

    main_module.main()

    assert lifecycle_manager.start_calls == 1
    assert lifecycle_manager.shutdown_paths == [
        "data/runtime_state_v2.json"
    ]

    assert FakeArmsCore.started is True
    assert FakeMarketConnector.connected is True

    assert FakePipeline.received_stages is not None
    assert len(FakePipeline.received_stages) == 9

    assert FakePipeline.received_context is not None
    assert "collector" in FakePipeline.received_context
    assert "settings" in FakePipeline.received_context


def test_main_stops_runtime_when_pipeline_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle_manager = FakeLifecycleManager()

    configure_fakes(
        monkeypatch,
        lifecycle_manager,
    )

    FakePipeline.should_fail = True

    with pytest.raises(
        RuntimeError,
        match="pipeline failure",
    ):
        main_module.main()

    assert lifecycle_manager.start_calls == 1
    assert lifecycle_manager.shutdown_paths == [
        "data/runtime_state_v2.json"
    ]


def test_main_does_not_shutdown_when_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingLifecycleManager(
        FakeLifecycleManager
    ):
        def start_clean(
            self,
        ) -> dict[str, object]:
            self.start_calls += 1

            raise RuntimeError(
                "startup failure"
            )

    lifecycle_manager = FailingLifecycleManager()

    configure_fakes(
        monkeypatch,
        lifecycle_manager,
    )

    with pytest.raises(
        RuntimeError,
        match="startup failure",
    ):
        main_module.main()

    assert lifecycle_manager.start_calls == 1
    assert lifecycle_manager.shutdown_paths == []
