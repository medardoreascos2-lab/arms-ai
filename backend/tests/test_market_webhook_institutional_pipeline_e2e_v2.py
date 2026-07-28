from datetime import datetime
from datetime import timedelta
from datetime import timezone

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.models.candle import Candle


START = datetime(
    2026,
    7,
    27,
    14,
    0,
    tzinfo=timezone.utc,
)


def timeframe_delta(
    timeframe: str,
) -> timedelta:
    values = {
        "1M": timedelta(minutes=1),
        "5M": timedelta(minutes=5),
        "15M": timedelta(minutes=15),
        "1H": timedelta(hours=1),
    }

    return values[timeframe]


def seed_timeframe(
    *,
    app,
    timeframe: str,
    candle_count: int,
    base_price: float,
    step: float,
) -> None:
    delta = timeframe_delta(
        timeframe
    )

    for index in range(
        candle_count
    ):
        close = (
            base_price
            + index * step
        )

        app.state.live_candle_store.add(
            Candle(
                symbol="NQ",
                timeframe=timeframe,
                open=close - 0.50,
                high=close + 1.50,
                low=close - 1.50,
                close=close,
                volume=(
                    1000.0
                    + index * 10.0
                ),
                timestamp=(
                    START
                    + delta * index
                ),
            )
        )


def build_final_webhook_payload() -> dict[
    str,
    object,
]:
    index = 49
    close = (
        23000.0
        + index * 2.0
    )

    return {
        "symbol": "NQ",
        "timeframe": "5m",
        "open": close - 0.50,
        "high": close + 1.50,
        "low": close - 1.50,
        "close": close,
        "volume": 1600.0,
        "timestamp": (
            START
            + timedelta(
                minutes=index * 5
            )
        ).isoformat(),
        "directional_momentum": 1.0,
        "adverse_structure": False,
    }


def test_webhook_runs_complete_institutional_pipeline():
    app = create_app()
    client = TestClient(
        app
    )

    seed_timeframe(
        app=app,
        timeframe="1M",
        candle_count=50,
        base_price=23000.0,
        step=2.0,
    )

    seed_timeframe(
        app=app,
        timeframe="15M",
        candle_count=50,
        base_price=22800.0,
        step=5.0,
    )

    seed_timeframe(
        app=app,
        timeframe="1H",
        candle_count=50,
        base_price=22000.0,
        step=20.0,
    )

    seed_timeframe(
        app=app,
        timeframe="5M",
        candle_count=49,
        base_price=23000.0,
        step=2.0,
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json=(
            build_final_webhook_payload()
        ),
    )

    assert response.status_code == 201

    webhook_result = response.json()

    assert webhook_result["status"] == "stored"
    assert webhook_result["count"] == 50
    assert (
        webhook_result[
            "analysis_generated"
        ]
        is True
    )

    analysis = (
        app.state.live_analysis_store
        .get_latest(
            symbol="NQ",
            timeframe="5m",
        )
    )

    assert analysis is not None
    assert analysis["symbol"] == "NQ"

    required_blocks = {
        "smart_money_v2",
        "market_context_v2",
        "multi_timeframe_v2",
        "probability_v2",
        "execution_v2",
        "decision_council_v2",
        "trade_plan_v2",
        "trade_validation_v2",
        "signal_v2",
        "trade_lifecycle_v2",
        "prepared_order_v2",
        "paper_execution_v2",
    }

    missing_blocks = sorted(
        required_blocks.difference(
            analysis.keys()
        )
    )

    assert missing_blocks == [], (
        "Faltan bloques del pipeline: "
        f"{missing_blocks}"
    )

    for key in required_blocks:
        assert analysis[key] is not None
        assert isinstance(
            analysis[key],
            dict,
        )

    multi_timeframe = analysis[
        "multi_timeframe_v2"
    ]

    assert (
        multi_timeframe["status"]
        == "READY"
    )

    assert (
        multi_timeframe["direction"]
        == "BULLISH"
    )

    assert (
        multi_timeframe[
            "ready_weight"
        ]
        == 1.0
    )

    market_context = analysis[
        "market_context_v2"
    ]

    assert (
        market_context["status"]
        == "READY"
    )

    assert market_context[
        "context"
    ] in {
        "BUY",
        "SELL",
        "NEUTRAL",
    }

    council = analysis[
        "decision_council_v2"
    ]

    assert council["decision"] in {
        "EXECUTE_LONG",
        "EXECUTE_SHORT",
        "WAIT",
        "BLOCK",
        "REJECT",
    }

    trade_plan = analysis[
        "trade_plan_v2"
    ]

    assert (
        trade_plan[
            "decision_authority"
        ]
        == "DECISION_COUNCIL_V2"
    )

    assert (
        trade_plan[
            "source_decision"
        ]
        == council["decision"]
    )

    assert (
        trade_plan[
            "source_execution_decision"
        ]
        == analysis[
            "execution_v2"
        ].get(
            "decision"
        )
    )

    assert "status" in analysis[
        "signal_v2"
    ]

    assert "status" in analysis[
        "prepared_order_v2"
    ]

    assert "status" in analysis[
        "paper_execution_v2"
    ]


def test_latest_analysis_contains_context_and_council():
    app = create_app()
    client = TestClient(
        app
    )

    for timeframe in (
        "1M",
        "15M",
        "1H",
    ):
        seed_timeframe(
            app=app,
            timeframe=timeframe,
            candle_count=50,
            base_price=22000.0,
            step=10.0,
        )

    seed_timeframe(
        app=app,
        timeframe="5M",
        candle_count=49,
        base_price=23000.0,
        step=2.0,
    )

    response = client.post(
        "/market/webhook",
        headers={
            "X-ARMS-TOKEN": str(
                app.state.webhook_token
            ),
        },
        json=(
            build_final_webhook_payload()
        ),
    )

    assert response.status_code == 201

    latest = client.get(
        "/market/latest-analysis",
        params={
            "symbol": "NQ",
            "timeframe": "5m",
        },
    )

    assert latest.status_code == 200

    analysis = latest.json()

    assert "market_context_v2" in analysis
    assert "multi_timeframe_v2" in analysis
    assert "decision_council_v2" in analysis
    assert "trade_plan_v2" in analysis
    assert "signal_v2" in analysis
    assert "paper_execution_v2" in analysis
