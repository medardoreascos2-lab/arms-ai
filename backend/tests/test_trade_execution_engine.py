from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.execution.trade_execution_engine import (
    TradeExecutionEngine,
)


def build_execution(
    *,
    action: str = "BUY",
    accepted: bool = True,
    status: str = "ACCEPTED",
) -> dict[str, object]:
    return {
        "symbol": "NQ",
        "timeframe": "5m",
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
        "generated_at": datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        ),
        "accepted": accepted,
        "status": status,
        "reason": "Señal oficial.",
    }


def test_executes_accepted_buy_in_simulated_mode():
    result = TradeExecutionEngine(
        mode="SIMULATED"
    ).execute(
        build_execution()
    )

    assert result["status"] == "SIMULATED"
    assert result["mode"] == "SIMULATED"
    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "5m"
    assert result["action"] == "BUY"
    assert result["entry_price"] == 21691.0
    assert result["stop_loss"] == 21672.25
    assert result["take_profit"] == 21728.50
    assert result["executed"] is True
    assert "executed_at" in result


def test_executes_accepted_sell():
    result = TradeExecutionEngine(
        mode="SIMULATED"
    ).execute(
        build_execution(
            action="SELL"
        )
    )

    assert result["action"] == "SELL"
    assert result["executed"] is True


def test_rejects_non_accepted_execution():
    engine = TradeExecutionEngine(
        mode="SIMULATED"
    )

    with pytest.raises(
        ValueError,
        match="accepted",
    ):
        engine.execute(
            build_execution(
                accepted=False,
                status="DUPLICATE",
            )
        )


def test_rejects_invalid_execution_status():
    engine = TradeExecutionEngine(
        mode="SIMULATED"
    )

    with pytest.raises(
        ValueError,
        match="status",
    ):
        engine.execute(
            build_execution(
                status="REJECTED",
            )
        )


def test_rejects_invalid_action():
    engine = TradeExecutionEngine(
        mode="SIMULATED"
    )

    with pytest.raises(
        ValueError,
        match="action",
    ):
        engine.execute(
            build_execution(
                action="WAIT",
            )
        )


def test_rejects_unsupported_mode():
    with pytest.raises(
        ValueError,
        match="mode",
    ):
        TradeExecutionEngine(
            mode="REAL"
        )


def test_rejects_missing_required_field():
    execution = build_execution()
    execution.pop("entry_price")

    with pytest.raises(
        KeyError,
        match="entry_price",
    ):
        TradeExecutionEngine(
            mode="SIMULATED"
        ).execute(
            execution
        )
