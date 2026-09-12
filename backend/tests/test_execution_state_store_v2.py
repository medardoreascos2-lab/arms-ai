from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
import json
from pathlib import Path

import pytest

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.services.execution_state_store_v2 import (
    ExecutionStateStoreV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)


def build_lifecycle_service() -> (
    TradeLifecycleServiceV2
):
    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.0,
            )
        ),
        position_manager=PositionManagerV2(
            point_value=2.0,
        ),
        trade_history_manager=(
            TradeHistoryManagerV2()
        ),
        performance_analytics=(
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
        ),
        starting_balance=17000.0,
        execution_risk_gate_v1=ExecutionRiskGateV1(
            validator=FakeApprovedValidator(),
            logger=RiskEventLoggerV1(),
        ),
    )


def build_store() -> ExecutionStateStoreV2:
    # Recovery fixtures must carry broker execution, journal and account proof.
    from backend.tests.test_durable_crash_recovery_v2 import build_runtime
    return build_runtime()[2]


def populate_store(store: ExecutionStateStoreV2) -> None:
    from backend.tests.test_durable_crash_recovery_v2 import open_position
    open_position(store.trade_lifecycle_service)


def test_captures_active_execution_state() -> None:
    store = build_store()
    populate_store(store)

    state = store.capture_state()

    assert state["schema_version"] == "2.0"

    assert state["summary"] == {
        "active_positions": 1,
        "active_protections": 1,
        "active_oco_groups": 1,
    }

    assert len(
        state["active_positions"]
    ) == 1

    assert len(
        state[
            "protective_registry"
        ]["protections"]
    ) == 1

    assert len(
        state["oco_manager"]["groups"]
    ) == 1


def test_validates_consistent_state() -> None:
    store = build_store()
    populate_store(store)

    state = store.capture_state()

    validated = store.validate_state(
        state=state,
    )

    assert validated["summary"] == {
        "active_positions": 1,
        "active_protections": 1,
        "active_oco_groups": 1,
    }


def test_restores_execution_state() -> None:
    source = build_store()
    populate_store(source)

    state = source.capture_state()

    target = build_store()

    result = target.restore_state(
        state=state,
    )

    assert result["restored"] is True
    assert result["active_positions"] == 1
    assert result["active_protections"] == 1
    assert result["active_oco_groups"] == 1

    restored_positions = (
        target.trade_lifecycle_service
        .get_active_positions()
    )

    restored_protections = (
        target.protective_order_registry
        .list_protections(
            status="ACTIVE",
        )
    )

    restored_groups = (
        target.oco_manager.list_groups(
            status="ACTIVE",
        )
    )

    assert len(restored_positions) == 1
    assert len(restored_protections) == 1
    assert len(restored_groups) == 1

    position = restored_positions[0]
    protection = restored_protections[0]
    group = restored_groups[0]

    assert (
        position["position_id"]
        == protection["position_id"]
        == group["position_id"]
    )

    assert (
        position["stop_order_id"]
        == protection["stop_order_id"]
        == group["stop_order_id"]
    )

    assert (
        position["take_profit_order_id"]
        == protection[
            "take_profit_order_id"
        ]
        == group[
            "take_profit_order_id"
        ]
    )


def test_saves_and_loads_state_file(
    tmp_path: Path,
) -> None:
    store = build_store()
    populate_store(store)

    state_file = (
        tmp_path / "execution-state.json"
    )

    result = store.save_to_file(
        file_path=state_file,
    )

    assert result["saved"] is True
    assert state_file.is_file()
    assert result["bytes_written"] > 0

    loaded = store.load_from_file(
        file_path=state_file,
    )

    assert loaded["schema_version"] == "2.0"
    assert loaded["summary"] == {
        "active_positions": 1,
        "active_protections": 1,
        "active_oco_groups": 1,
    }


def test_restores_from_state_file(
    tmp_path: Path,
) -> None:
    source = build_store()
    populate_store(source)

    state_file = (
        tmp_path / "execution-state.json"
    )

    source.save_to_file(
        file_path=state_file,
    )

    target = build_store()

    result = target.restore_from_file(
        file_path=state_file,
    )

    assert result["restored"] is True

    assert len(
        target.trade_lifecycle_service
        .get_active_positions()
    ) == 1

    assert len(
        target.protective_order_registry
        .list_protections(
            status="ACTIVE",
        )
    ) == 1

    assert len(
        target.oco_manager.list_groups(
            status="ACTIVE",
        )
    ) == 1


def test_rejects_invalid_schema_version() -> None:
    store = build_store()
    populate_store(store)

    state = store.capture_state()
    state["schema_version"] = "1.0"

    with pytest.raises(
        ValueError,
        match="schema_version",
    ):
        store.validate_state(
            state=state,
        )


def test_rejects_missing_position_reference() -> None:
    store = build_store()
    populate_store(store)

    state = store.capture_state()

    state[
        "protective_registry"
    ]["protections"][0][
        "position_id"
    ] = "position-missing"

    with pytest.raises(
        ValueError,
        match="posición inexistente",
    ):
        store.validate_state(
            state=state,
        )


def test_rejects_inconsistent_order_ids() -> None:
    store = build_store()
    populate_store(store)

    state = store.capture_state()

    state[
        "oco_manager"
    ]["groups"][0][
        "stop_order_id"
    ] = "different-stop-order"

    with pytest.raises(
        ValueError,
        match="stop_order_id inconsistente",
    ):
        store.validate_state(
            state=state,
        )


def test_rejects_restore_into_non_empty_runtime(
) -> None:
    source = build_store()
    populate_store(source)

    state = source.capture_state()

    target = build_store()
    populate_store(target)

    with pytest.raises(
        ValueError,
        match="posiciones activas",
    ):
        target.restore_state(
            state=state,
        )


def test_rejects_invalid_json_file(
    tmp_path: Path,
) -> None:
    store = build_store()

    state_file = (
        tmp_path / "invalid-state.json"
    )

    state_file.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="JSON válido",
    ):
        store.load_from_file(
            file_path=state_file,
        )


def test_rejects_missing_state_file(
    tmp_path: Path,
) -> None:
    store = build_store()

    missing_file = (
        tmp_path / "missing-state.json"
    )

    with pytest.raises(
        FileNotFoundError,
        match="No existe el archivo",
    ):
        store.load_from_file(
            file_path=missing_file,
        )


def test_saved_file_contains_valid_json(
    tmp_path: Path,
) -> None:
    store = build_store()
    populate_store(store)

    state_file = (
        tmp_path / "execution-state.json"
    )

    store.save_to_file(
        file_path=state_file,
    )

    raw_state = json.loads(
        state_file.read_text(
            encoding="utf-8",
        )
    )

    assert raw_state[
        "schema_version"
    ] == "2.0"

    assert raw_state["summary"][
        "active_positions"
    ] == 1

class FakeApprovedValidator:
    def validate_trade(
        self,
        contracts: int,
        risk_amount: float,
        symbol: str | None = None,
    ):
        return {
            "status": "APPROVED",
            "account": "TEST",
            "contracts": contracts,
            "risk_used": risk_amount,
        }
