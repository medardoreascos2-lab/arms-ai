from dataclasses import FrozenInstanceError

import pytest

from backend.config_settings import ArmsSettings
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.oco_manager_v2 import (
    OCOManagerV2,
)
from backend.execution.protective_order_registry_v2 import (
    ProtectiveOrderRegistryV2,
)
from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)
from backend.services.graceful_shutdown_service_v2 import (
    GracefulShutdownServiceV2,
)
from backend.services.runtime_context_v2 import (
    RuntimeContextV2,
    build_runtime_context,
)
from backend.services.runtime_lifecycle_manager_v2 import (
    RuntimeLifecycleManagerV2,
)
from backend.services.startup_coordinator_v2 import (
    StartupCoordinatorV2,
)
from backend.services.state_recovery_service_v2 import (
    StateRecoveryServiceV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def test_builds_complete_runtime_context() -> None:
    context = build_runtime_context()

    assert isinstance(
        context,
        RuntimeContextV2,
    )
    assert isinstance(
        context.execution_manager,
        ExecutionManagerV2,
    )
    assert isinstance(
        context.protective_order_registry,
        ProtectiveOrderRegistryV2,
    )
    assert isinstance(
        context.oco_manager,
        OCOManagerV2,
    )
    assert isinstance(
        context.trade_lifecycle_service,
        TradeLifecycleServiceV2,
    )
    assert isinstance(
        context.execution_state_store,
        ExecutionStateStoreV2,
    )
    assert isinstance(
        context.state_recovery_service,
        StateRecoveryServiceV2,
    )
    assert isinstance(
        context.startup_coordinator,
        StartupCoordinatorV2,
    )
    assert isinstance(
        context.graceful_shutdown_service,
        GracefulShutdownServiceV2,
    )
    assert isinstance(
        context.runtime_lifecycle_manager,
        RuntimeLifecycleManagerV2,
    )


def test_uses_supplied_settings() -> None:
    settings = ArmsSettings(
        account_balance=25000.0,
        point_value=5.0,
    )

    context = build_runtime_context(
        settings=settings,
    )

    assert context.settings is settings

    assert (
        context.trade_lifecycle_service
        .starting_balance
        == 25000.0
    )

    assert (
        context.position_manager.point_value
        == 5.0
    )


def test_shares_protective_registry() -> None:
    context = build_runtime_context()

    assert (
        context.trade_lifecycle_service
        .protective_order_registry_v2
        is context.protective_order_registry
    )

    assert (
        context.execution_state_store
        .protective_order_registry
        is context.protective_order_registry
    )


def test_shares_oco_manager() -> None:
    context = build_runtime_context()

    assert (
        context.trade_lifecycle_service
        .oco_manager_v2
        is context.oco_manager
    )

    assert (
        context.execution_state_store
        .oco_manager
        is context.oco_manager
    )


def test_shares_trade_lifecycle_service() -> None:
    context = build_runtime_context()

    assert (
        context.execution_state_store
        .trade_lifecycle_service
        is context.trade_lifecycle_service
    )


def test_runtime_starts_clean() -> None:
    context = build_runtime_context()

    report = (
        context.runtime_lifecycle_manager
        .start_clean()
    )

    assert report["success"] is True

    assert (
        context.runtime_lifecycle_manager
        .get_status()
        == "RUNNING"
    )


def test_runtime_starts_and_shuts_down(
    tmp_path,
) -> None:
    context = build_runtime_context()

    context.runtime_lifecycle_manager.start_clean()

    state_path = (
        tmp_path / "runtime-state.json"
    )

    report = (
        context.runtime_lifecycle_manager
        .shutdown_to(
            file_path=state_path,
        )
    )

    assert report["success"] is True
    assert state_path.exists()

    assert (
        context.runtime_lifecycle_manager
        .get_status()
        == "STOPPED"
    )


def test_context_is_frozen() -> None:
    context = build_runtime_context()

    with pytest.raises(FrozenInstanceError):
        context.settings = ArmsSettings()
