from copy import deepcopy
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.executable_signal_store import (
    ExecutableSignalStore,
)


def build_execution(
    *,
    symbol: str = "NQ",
    timeframe: str = "5m",
    action: str = "BUY",
    accepted: bool = True,
    status: str = "ACCEPTED",
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if generated_at is None:
        generated_at = datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "approved": True,
        "score": 88.0,
        "grade": "A+",
        "probability": 84.0,
        "confidence": "MUY ALTA",
        "risk_approved": True,
        "entry_price": 21691.0,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
        "generated_at": generated_at,
        "accepted": accepted,
        "status": status,
        "reason": "Señal oficial.",
    }


def test_saves_accepted_execution():
    store = ExecutableSignalStore()

    execution = build_execution()

    store.save(execution)

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert result is not None
    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"
    assert result["action"] == "BUY"


def test_rejects_non_accepted_execution():
    store = ExecutableSignalStore()

    with pytest.raises(
        ValueError,
        match="accepted",
    ):
        store.save(
            build_execution(
                accepted=False,
                status="DUPLICATE",
            )
        )


def test_replaces_previous_execution():
    store = ExecutableSignalStore()

    first_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    second_time = (
        first_time
        + timedelta(minutes=20)
    )

    store.save(
        build_execution(
            action="BUY",
            generated_at=first_time,
        )
    )

    store.save(
        build_execution(
            action="SELL",
            generated_at=second_time,
        )
    )

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert result is not None
    assert result["action"] == "SELL"
    assert result["generated_at"] == second_time


def test_keeps_markets_separated():
    store = ExecutableSignalStore()

    store.save(
        build_execution(
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.save(
        build_execution(
            symbol="ES",
            timeframe="1m",
        )
    )

    nq = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    es = store.get_latest(
        symbol="ES",
        timeframe="1m",
    )

    assert nq is not None
    assert es is not None
    assert nq["symbol"] == "NQ"
    assert es["symbol"] == "ES"


def test_returns_none_when_missing():
    store = ExecutableSignalStore()

    assert (
        store.get_latest(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )


def test_returns_defensive_copy():
    store = ExecutableSignalStore()

    execution = build_execution()
    store.save(execution)

    first = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert first is not None

    modified = deepcopy(first)
    modified["action"] = "SELL"

    first["action"] = "WAIT"

    second = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert second is not None
    assert second["action"] == "BUY"
