from pathlib import Path

from backend.api.app import create_app
from backend.risk.risk_event_logger_v1 import (
    RiskEventLoggerV1,
)
from backend.risk.risk_event_store_v2 import (
    RiskEventStoreV2,
)


def test_runtime_uses_shared_persistent_risk_logger(
    tmp_path: Path,
) -> None:
    path = tmp_path / "risk_events.json"

    app = create_app(
        risk_event_store_path_v2=path,
    )

    store = app.state.risk_event_store_v2
    logger = app.state.risk_event_logger_v1
    gate = app.state.execution_risk_gate_v1

    assert isinstance(
        store,
        RiskEventStoreV2,
    )

    assert isinstance(
        logger,
        RiskEventLoggerV1,
    )

    assert logger.store is store
    assert gate.logger is logger

    event = {
        "event_type": "TEST_RUNTIME_PERSISTENCE",
        "symbol": "NQ",
        "status": "APPROVED",
    }

    logged = logger.log_event(event)

    assert path.exists()

    persisted = RiskEventStoreV2(
        path=path,
    ).get_events()

    assert len(persisted) == 1
    assert persisted[0] == logged


def test_runtime_restores_persisted_risk_events(
    tmp_path: Path,
) -> None:
    path = tmp_path / "risk_events.json"

    first_app = create_app(
        risk_event_store_path_v2=path,
    )

    first_logger = (
        first_app.state
        .risk_event_logger_v1
    )

    first_logger.log_event(
        {
            "event_type": "RESTORE_TEST",
            "symbol": "MNQ",
            "status": "BLOCKED",
        }
    )

    second_app = create_app(
        risk_event_store_path_v2=path,
    )

    second_logger = (
        second_app.state
        .risk_event_logger_v1
    )

    events = second_logger.get_events()

    assert len(events) == 1
    assert events[0]["event_type"] == "RESTORE_TEST"
    assert events[0]["symbol"] == "MNQ"
    assert events[0]["status"] == "BLOCKED"


def test_runtime_risk_api_and_gate_share_logger(
    tmp_path: Path,
) -> None:
    path = tmp_path / "risk_events.json"

    app = create_app(
        risk_event_store_path_v2=path,
    )

    logger = app.state.risk_event_logger_v1
    gate = app.state.execution_risk_gate_v1

    assert gate.logger is logger

    logger.log_event(
        {
            "event_type": "SHARED_IDENTITY_TEST",
            "symbol": "NQ",
            "status": "APPROVED",
        }
    )

    assert (
        gate.get_risk_events()
        ==
        logger.get_events()
    )
