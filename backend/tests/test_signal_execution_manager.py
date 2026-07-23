from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
)


def build_signal(
    *,
    action: str = "BUY",
    approved: bool = True,
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
        "symbol": "NQ",
        "timeframe": "5m",
        "action": action,
        "approved": approved,
        "score": 88.0,
        "grade": "A+",
        "probability": 84.0,
        "confidence": "MUY ALTA",
        "risk_approved": True,
        "entry_price": 21691.0,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
        "reason": "Señal de prueba.",
        "generated_at": generated_at,
    }


def test_accepts_first_approved_signal():
    manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    result = manager.evaluate(
        build_signal()
    )

    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"
    assert result["action"] == "BUY"


def test_rejects_wait_signal():
    manager = SignalExecutionManager()

    result = manager.evaluate(
        build_signal(
            action="WAIT",
            approved=False,
        )
    )

    assert result["accepted"] is False
    assert result["status"] == "REJECTED"
    assert result["reason"] == "WAIT signal"


def test_rejects_unapproved_signal():
    manager = SignalExecutionManager()

    result = manager.evaluate(
        build_signal(
            approved=False,
        )
    )

    assert result["accepted"] is False
    assert result["status"] == "REJECTED"
    assert result["reason"] == "Signal not approved"


def test_rejects_duplicate_inside_cooldown():
    manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    first_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    manager.evaluate(
        build_signal(
            action="BUY",
            generated_at=first_time,
        )
    )

    result = manager.evaluate(
        build_signal(
            action="BUY",
            generated_at=(
                first_time
                + timedelta(minutes=5)
            ),
        )
    )

    assert result["accepted"] is False
    assert result["status"] == "DUPLICATE"
    assert result["reason"] == "Signal inside cooldown"


def test_accepts_same_action_after_cooldown():
    manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    first_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    manager.evaluate(
        build_signal(
            action="BUY",
            generated_at=first_time,
        )
    )

    result = manager.evaluate(
        build_signal(
            action="BUY",
            generated_at=(
                first_time
                + timedelta(minutes=16)
            ),
        )
    )

    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"


def test_accepts_direction_change_inside_cooldown():
    manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    first_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    manager.evaluate(
        build_signal(
            action="BUY",
            generated_at=first_time,
        )
    )

    result = manager.evaluate(
        build_signal(
            action="SELL",
            generated_at=(
                first_time
                + timedelta(minutes=5)
            ),
        )
    )

    assert result["accepted"] is True
    assert result["status"] == "ACCEPTED"
    assert result["action"] == "SELL"


def test_keeps_markets_separated():
    manager = SignalExecutionManager(
        cooldown_minutes=15
    )

    first_time = datetime(
        2026,
        7,
        22,
        9,
        30,
        tzinfo=timezone.utc,
    )

    manager.evaluate(
        build_signal(
            generated_at=first_time,
        )
    )

    other_market = build_signal(
        generated_at=(
            first_time
            + timedelta(minutes=5)
        )
    )

    other_market["symbol"] = "ES"

    result = manager.evaluate(
        other_market
    )

    assert result["accepted"] is True


def test_rejects_invalid_cooldown():
    with pytest.raises(
        ValueError,
        match="cooldown_minutes",
    ):
        SignalExecutionManager(
            cooldown_minutes=-1
        )
