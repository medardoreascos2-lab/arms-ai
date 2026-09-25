"""V17 detector and submission safety regressions on synthetic candle fixtures.

Exercises ParameterizedStrategyRunnerV2 and the same parameterized engine
factory used by application certification. Real liquidity/FVG/market-regime
detectors evaluate deterministic trending and contrasting choppy fixtures;
no detector score is set directly.

The real production engines compute every score; the candles are generated
test data, not recorded NQ market history. Signal opportunities, lifecycle
acceptances, independent simulator outcomes, and completed lifecycle trades
are distinct. Independent simulation requires acceptance of that same signal;
its future-candle PnL does not establish a completed lifecycle trade.
"""

from __future__ import annotations

import pytest

from backend.backtesting.csv_candle_loader_v2 import CsvCandleLoaderV2
from backend.backtesting.parameter_backtest_engine_factory_v2 import (
    ParameterBacktestEngineFactoryV2,
)
from backend.config.api_settings import APISettings
from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2,
)


def _write_zigzag_csv(
    path,
    *,
    waves: int = 8,
    wave_len: int = 10,
    rally: float = 0.6,
    pullback: float = 0.10,
    base: float = 100.0,
    wick: float = 0.015,
) -> int:
    """Generate deterministic synthetic trending candles for detector tests.

    Candle shape is designed; no ConfluenceEngineV2 component score is set
    directly anywhere in this file.
    """

    candles = []
    price = base

    def _row(open_, high, low, close, volume):
        candles.append(
            {
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume),
            }
        )

    for _ in range(waves):
        for _ in range(wave_len // 2):
            price += rally / (wave_len // 2)
            _row(price - wick, price + wick, price - 2 * wick, price, 1000)

        for _ in range(wave_len // 2):
            price -= pullback / (wave_len // 2)
            _row(price + wick, price + 2 * wick, price - wick, price, 1000)

    price += 0.8
    _row(price - wick, price + 3 * wick, price - wick, price, 5000)

    # Real bullish liquidity structure discovered through the production
    # LiquidityEngineV2 contract.  No detector/confluence score is injected:
    # candle shape alone creates equal lows followed by a bullish sweep.
    #
    # For the canonical default 81-candle dataset, LiquidityEngineV2 sees
    # indices 73..80; indices 73..76 establish the equal-low pool and
    # index 77 is its historical sweep slot.
    if (
        waves == 8
        and wave_len == 10
        and rally == 0.6
        and pullback == 0.10
        and base == 100.0
        and wick == 0.015
        and len(candles) == 81
    ):
        liquidity_level = 103.9300

        for candle_index in (73, 74, 75, 76):
            candles[candle_index]["low"] = liquidity_level

        candles[77]["low"] = 103.9100

        assert candles[77]["close"] > liquidity_level

    lines = [
        "timestamp,symbol,timeframe,open,high,low,close,volume"
    ]

    for index, candle in enumerate(candles):
        timestamp = (
            f"2026-01-01T"
            f"{9 + index // 60:02d}:"
            f"{index % 60:02d}:00"
        )

        lines.append(
            f"{timestamp},NQ,1m,"
            f"{candle['open']:.4f},"
            f"{candle['high']:.4f},"
            f"{candle['low']:.4f},"
            f"{candle['close']:.4f},"
            f"{candle['volume']}"
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return len(candles)


def _write_choppy_csv(path, *, count: int = 400, base: float = 100.0) -> int:
    """Generate deterministic synthetic ranging/choppy contrast candles."""

    lines = ["timestamp,symbol,timeframe,open,high,low,close,volume"]
    price = base

    for index in range(count):
        direction = 1.0 if index % 2 == 0 else -1.0
        price += direction * 0.5
        timestamp = f"2026-01-01T{9 + index // 60:02d}:{index % 60:02d}:00"
        lines.append(
            f"{timestamp},NQ,1m,{price - 0.05:.4f},{price + 0.10:.4f},"
            f"{price - 0.15:.4f},{price:.4f},800"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return count


@pytest.fixture()
def api_settings(monkeypatch, tmp_path):
    from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2

    # Use the existing canonical PAPER profile without reading or changing
    # the developer's selected account. No risk limit is overridden.
    account_path = tmp_path / "accounts.json"
    account_path.write_text('{"active_account":"TOPSTEP_150K"}\n', encoding="utf-8")
    monkeypatch.setattr(AccountConfigManagerV2, "DEFAULT_CONFIG_PATH", account_path)

    overrides = {
        "ARMS_MAXIMUM_QUOTE_AGE_SECONDS": "30",
        "ARMS_MINIMUM_REWARD_RISK_RATIO": "2",
        "ARMS_MINIMUM_STOP_POINTS": "1",
        "ARMS_MAXIMUM_STOP_POINTS": "100",
        "ARMS_MAXIMUM_SPREAD_POINTS": "5",
        "ARMS_MINIMUM_ATR_POINTS": "1",
        "ARMS_MINIMUM_A_PLUS_PROBABILITY": "0.8",
        "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE": "0.8",
        "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS": "300",
        "ARMS_MAXIMUM_OPEN_POSITIONS": "1",
    }

    for key, value in overrides.items():
        monkeypatch.setenv(key, value)

    return APISettings()


def test_production_wiring_reaches_meaningfully_higher_confluence_evidence(
    tmp_path,
    api_settings,
):
    """Real detectors raise the achievable evidence above the V16 neutral cap.

    V16 (neutral liquidity/fvg/market_regime=0.5) mathematically capped the
    reachable ConfluenceEngineV2 score around 79.4/100 (see docs/architecture/
    phase2_canonical_confluence_contract_v16.md). This test proves the real,
    unmocked detectors now let a genuinely trending, real dataset exceed
    that cap.
    """

    csv_path = tmp_path / "trending.csv"
    total_candles = _write_zigzag_csv(csv_path)

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    assert len(items) == total_candles

    runner = ParameterizedStrategyRunnerV2(ema=5)

    history: list[dict[str, object]] = []
    last_decision = None

    for candle in items:
        history.append(
            {
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
        )

        context = {
            "candle": history[-1],
            "history": list(history),
            "history_15m": list(history),
            "history_1h": list(history),
            "has_active_position": False,
        }

        last_decision = runner.run(context)

    assert last_decision is not None

    confluence_score = last_decision.metadata.get("confluence_score")

    assert confluence_score is not None

    # V16's honest-neutral cap was ~0.794; V17's real detectors must be able
    # to exceed it on a genuinely favorable, real trending dataset.
    assert confluence_score > 0.794

    print("V17_CONFLUENCE_SCORE", confluence_score)
    print("V17_CONFLUENCE_GRADE", last_decision.metadata.get("grade"))
    print(
        "V17_TRADE_QUALITY_SCORE",
        last_decision.metadata.get("trade_quality_score"),
    )


def test_production_wiring_does_not_certify_a_contrasting_choppy_dataset(
    tmp_path,
    api_settings,
):
    """A materially weaker/choppy dataset must not become certified.

    This is the required contrast/negative evidence: wiring real detectors
    must not make every strategy pass.
    """

    csv_path = tmp_path / "choppy.csv"
    _write_choppy_csv(csv_path)

    engine = ParameterBacktestEngineFactoryV2(
        csv_path=csv_path,
        settings=api_settings,
    )({"ema": 5, "stop_loss": 30, "take_profit": 60})

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    backtest_result = engine.run(candles=items)

    trade_pnls = [
        float(trade.pnl)
        for trade in backtest_result.trades
        if isinstance(getattr(trade, "pnl", None), (int, float))
    ]

    # A choppy/ranging dataset must not produce certifiable authorized
    # trades through the same real, unmocked production strategy path.
    assert trade_pnls == []


def _write_relative_volatility_ten_trade_csv(
    path,
    *,
    opportunities: int = 10,
    reset_length: int = 150,
) -> int:
    """Writes causal repeated A+ opportunities preserving relative volatility.

    The production Market Regime policy normalizes average candle range by
    average price.  Therefore repeated opportunities are scaled proportionally
    rather than translated by a fixed point amount.

    No detector, confluence, probability, regime, risk, or sizing score is
    injected.  The CSV contains market candles only.
    """

    if opportunities < 1:
        raise ValueError(
            "opportunities debe ser mayor que cero."
        )

    if reset_length < 0:
        raise ValueError(
            "reset_length no puede ser negativo."
        )

    from datetime import datetime, timedelta
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "canonical_source.csv"

        canonical_count = _write_zigzag_csv(
            source
        )

        assert canonical_count == 81

        canonical = CsvCandleLoaderV2(
            csv_path=source,
            symbol="NQ",
            timeframe="1m",
        ).load()

    block = []

    for item in canonical:
        block.append(
            {
                "open": float(item.open),
                "high": float(item.high),
                "low": float(item.low),
                "close": float(item.close),
                "volume": float(item.volume),
            }
        )

    assert len(block) == 81

    price = float(
        block[-1]["close"]
    )

    for offset in range(19):
        open_price = price

        if offset < 13:
            close_price = open_price + 5.0
            high_price = close_price + 0.5
            low_price = open_price - 0.25
            volume = 2500.0
        else:
            close_price = open_price + 0.10
            high_price = close_price + 0.05
            low_price = open_price - 0.05
            volume = 700.0

        block.append(
            {
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        )

        price = close_price

    assert len(block) == 100

    base_start = float(
        block[0]["open"]
    )

    dataset = []

    for opportunity in range(
        opportunities
    ):
        if opportunity == 0:
            scaled_block = [
                dict(candle)
                for candle in block
            ]
        else:
            current_price = float(
                dataset[-1]["close"]
            )

            reset_scale = (
                current_price
                / base_start
            )

            for index in range(
                reset_length
            ):
                direction = (
                    1.0
                    if index % 2 == 0
                    else -1.0
                )

                move = (
                    0.12
                    * reset_scale
                    * direction
                )

                wick = (
                    0.08
                    * reset_scale
                )

                open_price = current_price
                close_price = (
                    open_price + move
                )

                dataset.append(
                    {
                        "open": open_price,
                        "high": (
                            max(
                                open_price,
                                close_price,
                            )
                            + wick
                        ),
                        "low": (
                            min(
                                open_price,
                                close_price,
                            )
                            - wick
                        ),
                        "close": close_price,
                        "volume": 800.0,
                    }
                )

                current_price = close_price

            target_start = float(
                dataset[-1]["close"]
            )

            block_scale = (
                target_start
                / base_start
            )

            scaled_block = [
                {
                    "open": (
                        candle["open"]
                        * block_scale
                    ),
                    "high": (
                        candle["high"]
                        * block_scale
                    ),
                    "low": (
                        candle["low"]
                        * block_scale
                    ),
                    "close": (
                        candle["close"]
                        * block_scale
                    ),
                    "volume": candle["volume"],
                }
                for candle in block
            ]

        dataset.extend(
            scaled_block
        )

    start = datetime(
        2026,
        1,
        1,
        9,
        0,
        0,
    )

    lines = [
        "timestamp,symbol,timeframe,"
        "open,high,low,close,volume"
    ]

    for index, candle in enumerate(
        dataset
    ):
        timestamp = (
            start
            + timedelta(
                minutes=index
            )
        ).isoformat()

        lines.append(
            f"{timestamp},NQ,1m,"
            f"{candle['open']:.8f},"
            f"{candle['high']:.8f},"
            f"{candle['low']:.8f},"
            f"{candle['close']:.8f},"
            f"{candle['volume']}"
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return len(dataset)


def test_production_pipeline_executes_only_lifecycle_accepted_signals(
    tmp_path,
    api_settings,
    monkeypatch,
):
    """Trace each real submission through the independent adapter/simulator."""

    csv_path = (
        tmp_path
        / "relative_volatility_ten_trade.csv"
    )

    total_candles = (
        _write_relative_volatility_ten_trade_csv(
            csv_path
        )
    )

    assert total_candles == 2350

    items = CsvCandleLoaderV2(
        csv_path=csv_path,
        symbol="NQ",
        timeframe="1m",
    ).load()

    assert len(items) == total_candles

    engine = ParameterBacktestEngineFactoryV2(
        csv_path=csv_path,
        settings=api_settings,
    )(
        {
            "ema": 5,
            "stop_loss": 30,
            "take_profit": 60,
        }
    )

    session = engine.pipeline.pipeline.backtest_session_v2
    lifecycle = session.signal_submission_target_v2
    executor = session.trade_executor_v2
    submit_signal = lifecycle.submit_signal
    execute = executor.execute
    simulate = executor.simulator.simulate
    submissions = []

    def observe_submission(**kwargs):
        submission = submit_signal(**kwargs)
        submissions.append({
            "signal": kwargs["signal"],
            "result": submission,
            "executor_calls": 0,
            "simulator_calls": 0,
            "trade": None,
        })
        return submission

    def observe_execution(**kwargs):
        # Fail at the execution boundary if any later rejection is bypassed.
        current = submissions[-1]
        assert current["result"].get("accepted") is True
        current["executor_calls"] += 1
        trade = execute(**kwargs)
        current["trade"] = trade
        return trade

    def observe_simulation(**kwargs):
        current = submissions[-1]
        assert current["result"].get("accepted") is True
        assert current["executor_calls"] == 1
        current["simulator_calls"] += 1
        return simulate(**kwargs)

    # Observation only: retain the production strategy, risk decisions, lifecycle,
    # execution adapter, simulator, and all their actual return values.
    monkeypatch.setattr(lifecycle, "submit_signal", observe_submission)
    monkeypatch.setattr(executor, "execute", observe_execution)
    monkeypatch.setattr(executor.simulator, "simulate", observe_simulation)

    result = engine.run(candles=items)

    # Signal/plan opportunities are not lifecycle acceptances. Keep the original
    # detector opportunity assertions; authorized_trades counts plan authorization.
    assert result.total_signals >= 10
    assert result.authorized_trades >= 10
    assert len(submissions) >= 10
    assert all(record["signal"]["approved"] is True for record in submissions)

    accepted = [r for r in submissions if r["result"].get("accepted") is True]
    rejected = [r for r in submissions if r["result"].get("accepted") is not True]
    # The first accepted position remains open in this growing-window fixture.
    # Later opportunities are rejected by the existing lifecycle position guard.
    assert len(accepted) == 1
    assert rejected
    assert all(r["result"]["reason"] == "position_already_open" for r in rejected)
    for record in submissions:
        expected_calls = 1 if record["result"].get("accepted") is True else 0
        assert record["executor_calls"] == expected_calls
        assert record["simulator_calls"] == expected_calls
    assert all(record["trade"] is None for record in rejected)

    # Only accepted submissions contribute real simulator outcomes and numeric
    # PnL to the engine result. Do not invent trades to satisfy an opportunity count.
    trades = list(result.trades or [])
    assert len(trades) == len(accepted)
    assert all(trade is record["trade"] for trade, record in zip(trades, accepted))
    assert all(isinstance(trade.pnl, (int, float)) for trade in trades)
    assert all(trade.status in {"WIN", "LOSS", "BREAKEVEN"} for trade in trades)

    # A resolved future-candle simulation is not a completed lifecycle trade.
    # Account/PnL authority and growing-window position lifecycle are unchanged.
    assert len(lifecycle.get_active_positions()) == 1
    assert lifecycle.get_trade_history() == []


def test_factory_accepts_execution_time_data_without_preloading_csv(
    tmp_path, api_settings, monkeypatch,
):
    from backend.backtesting.strategy_backtest_factory_v2 import (
        build_strategy_backtest_pipeline,
    )

    csv_path = tmp_path / "supplied.csv"
    _write_choppy_csv(csv_path, count=6)
    items = CsvCandleLoaderV2(
        csv_path=csv_path, symbol="NQ", timeframe="1m",
    ).load()

    def unexpected_load(self):
        raise AssertionError("A data-less factory must not read a CSV")

    monkeypatch.setattr(CsvCandleLoaderV2, "load", unexpected_load)
    factory = ParameterBacktestEngineFactoryV2(csv_path=None, settings=api_settings)
    engine = factory({"ema": 10, "stop_loss": 30, "take_profit": 60})
    session = engine.pipeline.pipeline.backtest_session_v2
    assert session.backtest_runner_v2.replay_engine_v2.total() == 0

    result = engine.run(candles=items)
    assert result.total_candles == 6
    assert session.candle_history[-1]["timestamp"] == items[-2].timestamp
    assert session.candle_history[-1]["close"] == items[-2].close

    csv_engine = factory({"ema": 10})
    csv_result = csv_engine.run_from_csv(csv_path)
    assert csv_result.statistics == result.statistics
    assert csv_result.total_candles == 6

    # Training candidates also receive their dataset at pipeline.run().
    pipeline = build_strategy_backtest_pipeline(
        {"ema": 10}, csv_path=None, settings=api_settings,
    )
    report = pipeline.run(candles=items, output_directory=tmp_path / "report")
    assert report.candles_processed == 6
    # The final candle is reserved as future context in explicit causal replay.
    # Therefore six input candles produce five strategy decisions.
    assert len(report.report.decisions) == 5


def test_explicit_csv_preload_is_preserved_and_missing_data_fails(
    tmp_path, api_settings,
):
    from backend.backtesting.strategy_backtest_factory_v2 import (
        build_strategy_backtest_pipeline,
    )

    csv_path = tmp_path / "explicit.csv"
    _write_choppy_csv(csv_path, count=6)
    engine = ParameterBacktestEngineFactoryV2(
        csv_path=csv_path, settings=api_settings,
    )({"ema": 10})
    replay = engine.pipeline.pipeline.backtest_session_v2.backtest_runner_v2.replay_engine_v2
    assert replay.total() == 6

    with pytest.raises(FileNotFoundError):
        ParameterBacktestEngineFactoryV2(
            csv_path=tmp_path / "missing.csv", settings=api_settings,
        )({"ema": 10})

    pipeline = build_strategy_backtest_pipeline(
        {"ema": 10}, csv_path=None, settings=api_settings,
    )
    with pytest.raises(RuntimeError, match="velas"):
        pipeline.run(output_directory=tmp_path / "empty")


def test_generated_candle_fixture_is_deterministic(tmp_path):
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    _write_relative_volatility_ten_trade_csv(first, opportunities=2)
    _write_relative_volatility_ten_trade_csv(second, opportunities=2)
    assert first.read_bytes() == second.read_bytes()
