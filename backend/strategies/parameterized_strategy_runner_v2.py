from __future__ import annotations

from types import SimpleNamespace

from backend.indicators.ema_engine import EMAEngine

from backend.market_structure.market_structure_engine_v3 import (
    MarketStructureEngineV3,
)

from backend.trend.trend_context_engine_v2 import (
    TrendContextEngineV2,
)

from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)

from backend.intelligence.trade_quality_engine_v1 import (
    TradeQualityEngineV1,
)

from backend.intelligence.position_filter_v1 import (
    PositionFilterV1,
)

from backend.market_analysis.market_regime_engine import (
    MarketRegimeEngine,
)

from backend.smart_money.liquidity_engine_v2 import (
    LiquidityEngineV2,
)

from backend.smart_money.smart_money_engine_v2 import (
    SmartMoneyEngineV2,
)

from backend.execution.position_lifecycle_manager_v1 import (
    PositionLifecycleManagerV1,
)

from backend.risk.signal_controller_v2 import (
    SignalControllerV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


def _direction_from_allowed(allowed_direction: str) -> str:
    return str(allowed_direction or "").strip().upper()


def _estimate_liquidity_score(engine, history, allowed_direction: str) -> float:
    """Real (non-fabricated) liquidity score from LiquidityEngineV2.

    Only the historical prefix already available at this decision point is
    passed in; no future candle is ever consulted (no lookahead). A neutral
    0.5 is returned when the real engine legitimately cannot evaluate yet
    (not enough history) or has no completed sweep to react to.
    """

    direction = _direction_from_allowed(allowed_direction)

    required = engine.lookback + 2

    if len(history) < required:
        return 0.5

    candles = [
        SimpleNamespace(
            high=float(item["high"]),
            low=float(item["low"]),
            close=float(item["close"]),
        )
        for item in history[-(engine.lookback + 3):]
    ]

    try:
        engine.analyze(candles)
    except ValueError:
        return 0.5

    if engine.sweep_detected != "SÍ":
        # Equal highs/lows are pending liquidity, not a completed reaction.
        return 0.5

    if (
        engine.sweep_direction == "ALCISTA"
        and direction == "LONG"
    ) or (
        engine.sweep_direction == "BAJISTA"
        and direction == "SHORT"
    ):
        return 1.0

    return 0.0


def _estimate_fvg_score(engine, history, allowed_direction: str) -> float:
    """Real (non-fabricated) FVG score from SmartMoneyEngineV2.detect_fvg.

    Uses only the three most recent historical candles (classic 3-candle
    FVG detection); never a future candle.
    """

    direction = _direction_from_allowed(allowed_direction)

    if len(history) < 3:
        return 0.5

    first, second, third = history[-3], history[-2], history[-1]

    result = engine.detect_fvg(
        first_high=float(first["high"]),
        first_low=float(first["low"]),
        second_high=float(second["high"]),
        second_low=float(second["low"]),
        third_high=float(third["high"]),
        third_low=float(third["low"]),
    )

    if not result["fvg"]:
        return 0.5

    if direction not in ("LONG", "SHORT"):
        return 0.0

    fvg_direction = {
        "BULLISH": "LONG",
        "BEARISH": "SHORT",
    }.get(result["direction"], "NONE")

    if fvg_direction == direction:
        return 1.0

    if fvg_direction == "NONE":
        return 0.25

    return 0.0


def _market_regime_inputs(history):
    """Real, no-lookahead directional/volatility/compression evidence.

    Mirrors backend/services/live_market_analysis_service.py's
    _evaluate_market_regime derivation exactly, using only the provided
    historical prefix.
    """

    closes = [float(item["close"]) for item in history]
    highs = [float(item["high"]) for item in history]
    lows = [float(item["low"]) for item in history]

    if len(closes) < 2:
        directional_strength = 0.0
    else:
        net_movement = closes[-1] - closes[0]
        total_movement = sum(
            abs(current - previous)
            for previous, current in zip(closes, closes[1:])
        )

        directional_strength = (
            0.0 if total_movement <= 0 else net_movement / total_movement
        )

    directional_strength = min(1.0, max(-1.0, directional_strength))

    average_price = sum(closes) / len(closes)
    average_range = sum(
        high - low for high, low in zip(highs, lows)
    ) / len(closes)

    volatility_score = (
        0.0
        if average_price <= 0
        else average_range / average_price * 1000.0
    )
    volatility_score = min(1.0, max(0.0, volatility_score))

    complete_range = max(highs) - min(lows)
    recent_window = min(10, len(history))
    recent_range = (
        max(highs[-recent_window:]) - min(lows[-recent_window:])
    )

    compression_score = (
        1.0
        if complete_range <= 0
        else 1.0 - min(1.0, recent_range / complete_range)
    )
    compression_score = min(1.0, max(0.0, compression_score))

    return directional_strength, volatility_score, compression_score


def _estimate_market_regime(engine, history):
    """Real (non-fabricated) market-regime evaluation for this candle.

    Returns the full regime dict (used for market_tradable) plus the
    ConfluenceEngineV2 market_regime_score derived from it, mirroring
    live_market_analysis_service.py's own regime-to-score translation.
    """

    if len(history) < 2:
        return None, 0.5, True

    directional_strength, volatility_score, compression_score = (
        _market_regime_inputs(history)
    )

    regime = engine.evaluate(
        directional_strength=directional_strength,
        volatility_score=volatility_score,
        compression_score=compression_score,
    )

    tradable = bool(regime.get("tradable", True))

    if not tradable:
        return regime, 0.0, tradable

    if regime.get("regime") in ("TREND_UP", "TREND_DOWN"):
        confidence = min(1.0, max(0.0, float(regime.get("confidence", 0.5))))
        return regime, confidence, tradable

    return regime, 0.5, tradable


def _estimate_volume_score(history) -> float:
    """Real (non-fabricated) volume score: latest candle vs trailing average.

    Returns a neutral 0.5 when volume data is unavailable instead of
    inventing a value.
    """

    volumes: list[float] = []

    for item in history[-20:]:
        raw_volume = (
            item.get("volume")
            if isinstance(item, dict)
            else getattr(item, "volume", None)
        )

        if raw_volume is None:
            continue

        try:
            volumes.append(float(raw_volume))
        except (TypeError, ValueError):
            continue

    if len(volumes) < 2:
        return 0.5

    average_volume = sum(volumes[:-1]) / len(volumes[:-1])

    if average_volume <= 0:
        return 0.5

    return max(
        0.0,
        min(
            1.0,
            volumes[-1] / average_volume / 2.0,
        ),
    )


class ParameterizedStrategyRunnerV2:
    """
    Runner de estrategia parametrizable para optimización.

    Utiliza historial de velas y EMA dinámica.
    """

    def __init__(
        self,
        *,
        ema: int,
        stop_loss: float = 50.0,
        take_profit: float = 100.0,
    ) -> None:

        self.ema = int(
            ema
        )

        self.stop_loss_points = float(
            stop_loss
        )

        self.take_profit_points = float(
            take_profit
        )

        if self.stop_loss_points <= 0:
            raise ValueError(
                "stop_loss debe ser mayor que cero."
            )

        if self.take_profit_points <= 0:
            raise ValueError(
                "take_profit debe ser mayor que cero."
            )

        self.calls = 0

        # Estado interno de la estrategia
        self.position_state = "FLAT"

        self.market_structure_engine = (
            MarketStructureEngineV3()
        )

        self.trend_context_engine = (
            TrendContextEngineV2()
        )

        self.confluence_engine = (
            ConfluenceEngineV2()
        )

        self.liquidity_engine = (
            LiquidityEngineV2(
                tolerance=1.0,
                lookback=5,
            )
        )

        self.smart_money_engine = (
            SmartMoneyEngineV2()
        )

        # Same reviewed thresholds as backend/tests/test_market_regime_engine.py.
        self.market_regime_engine = (
            MarketRegimeEngine(
                trend_threshold=0.60,
                high_volatility_threshold=0.80,
                low_volatility_threshold=0.20,
                compression_threshold=0.15,
            )
        )

        self.trade_quality_engine = (
            TradeQualityEngineV1()
        )

        self.position_filter = (
            PositionFilterV1()
        )

        self.position_lifecycle = (
            PositionLifecycleManagerV1()
        )

        self.signal_controller = (
            SignalControllerV2()
        )


    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        self.calls += 1

        candle = context.get(
            "candle",
            {},
        )


        current_price = float(
            candle.get(
                "close",
                0,
            )
        )


        if current_price > 0:

            lifecycle_result = (
                self.position_lifecycle.update(
                    current_price
                )
            )


            if lifecycle_result.closed:

                self.position_state = "FLAT"



        if context.get(
            "has_active_position",
            False,
        ):

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.5,
                reason="ACTIVE POSITION",
                metadata={},
            )


        history = context.get(
            "history",
            [],
        )


        market_structure = (
            self.market_structure_engine.analyze(
                history
            )
        )


        candles_15m = context.get(
            "history_15m",
            history,
        )


        candles_1h = context.get(
            "history_1h",
            history,
        )


        trend_context = (
            self.trend_context_engine.analyze(
                candles_1h,
                candles_15m,
            )
        )


        prices = [
            float(
                item["close"]
            )
            for item in history
            if "close" in item
        ]


        if len(prices) < self.ema:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.0,
                reason="NOT ENOUGH DATA FOR EMA",
            )


        ema_engine = EMAEngine(
            period=self.ema
        )

        ema_value = ema_engine.calculate(
            prices
        )


        previous_ema = ema_value


        if len(prices) > self.ema:

            previous_ema = ema_engine.calculate(
                prices[:-1]
            )


        entry_price = float(
            candle.get(
                "close",
                0,
            )
        )


        if entry_price <= 0:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.0,
                reason="NO PRICE",
            )



        bullish_score = 0
        bearish_score = 0


        candle_open = float(
            candle.get(
                "open",
                entry_price,
            )
        )


        # Tendencia EMA
        if entry_price > ema_value:
            bullish_score += 40

        if entry_price < ema_value:
            bearish_score += 40


        # Pendiente EMA
        if ema_value > previous_ema:
            bullish_score += 20

        if ema_value < previous_ema:
            bearish_score += 20


        # Confirmación de vela
        if candle_open < entry_price:
            bullish_score += 20

        if candle_open > entry_price:
            bearish_score += 20


        # Momentum simple
        if len(prices) >= 3:

            previous_price = prices[-3]

            if entry_price > previous_price:
                bullish_score += 20

            if entry_price < previous_price:
                bearish_score += 20




        # Market Structure
        if market_structure.trend == "BULLISH":

            bullish_score += 20


        if market_structure.trend == "BEARISH":

            bearish_score += 20



        # Break Of Structure (BOS)
        if market_structure.bos:

            if market_structure.trend == "BULLISH":

                bullish_score += 10


            if market_structure.trend == "BEARISH":

                bearish_score += 10




        ema_alignment = (
            entry_price > ema_value
            and trend_context.allowed_direction == "LONG"
        ) or (
            entry_price < ema_value
            and trend_context.allowed_direction == "SHORT"
        )


        # Canonical ConfluenceEngineV2 contract (see backend/services/
        # live_market_analysis_service.py._evaluate_confluence_v2 for the
        # authoritative live caller); translated here from the real signals
        # already computed above, including the real liquidity/FVG/market
        # regime authorities (V17). Each detector sees only the historical
        # prefix available at this decision point (no lookahead).
        trend_score = (
            1.0
            if trend_context.allowed_direction in ("LONG", "SHORT")
            else 0.50
        )

        structure_score = max(
            0.0,
            min(
                1.0,
                float(market_structure.score) / 100.0,
            ),
        )

        ema_alignment_score = 1.0 if ema_alignment else 0.0

        probability_score = max(
            0.0,
            min(
                1.0,
                max(bullish_score, bearish_score) / 100.0,
            ),
        )

        volume_score = _estimate_volume_score(history)

        liquidity_score = _estimate_liquidity_score(
            self.liquidity_engine,
            history,
            trend_context.allowed_direction,
        )

        fvg_score = _estimate_fvg_score(
            self.smart_money_engine,
            history,
            trend_context.allowed_direction,
        )

        _, market_regime_score, market_tradable = (
            _estimate_market_regime(
                self.market_regime_engine,
                history,
            )
        )

        confluence_payload = (
            self.confluence_engine.evaluate(
                trend_score=trend_score,
                structure_score=structure_score,
                liquidity_score=liquidity_score,
                fvg_score=fvg_score,
                ema_alignment_score=ema_alignment_score,
                market_regime_score=market_regime_score,
                probability_score=probability_score,
                volume_score=volume_score,
                risk_approved=True,
                sizing_approved=True,
                market_tradable=market_tradable,
            )
        )

        confluence = SimpleNamespace(
            allowed=bool(confluence_payload["approved"]),
            score=float(confluence_payload["score"]),
            grade=str(confluence_payload["grade"]),
            reasons=list(confluence_payload["blocking_reasons"]),
        )


        trade_quality = (
            self.trade_quality_engine.evaluate(
                confluence=confluence,
                market_structure=market_structure,
                trend_context=trend_context,
            )
        )



        # Trend Context Filter

        if trend_context.allowed_direction == "LONG":

            bearish_score = 0


        elif trend_context.allowed_direction == "SHORT":

            bullish_score = 0


        elif not trend_context.aligned:

            bullish_score -= 20
            bearish_score -= 20




        # ==============================
        # TRADE QUALITY HARD FILTER
        # ==============================

        if not trade_quality.approved:

            quality_reason = (
                trade_quality.reasons[0]
                if trade_quality.reasons
                else "TRADE QUALITY BLOCKED"
            )

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=(
                    trade_quality.score / 100
                ),
                reason=quality_reason,
                metadata={
                    "trade_quality_score": (
                        trade_quality.score / 100
                    ),
                    "trade_quality_reasons": (
                        trade_quality.reasons
                    ),
                    "confluence_score": (
                        confluence.score / 100
                    ),
                    "grade": confluence.grade,
                    "reasons": confluence.reasons,
                },
            )


        # ==============================
        # SIGNAL CONTROLLER FILTER
        # ==============================


        signal_direction = (
            trend_context.allowed_direction
        )


        signal_index = context.get(
            "signal_index"
        )

        if signal_index is None:
            current_index = len(history)
        else:
            current_index = int(
                signal_index
            )

            if current_index < 0:
                raise ValueError(
                    "signal_index no puede ser negativo."
                )


        signal_check = (
            self.signal_controller.evaluate(
                current_index=current_index,
                direction=signal_direction,
                grade=confluence.grade,
            )
        )


        if not signal_check.allowed:

            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=0.5,
                reason=signal_check.reason,
                metadata={},
            )



        # ==============================
        # CONFLUENCE ENGINE FINAL FILTER
        # ==============================


        if (
            confluence.allowed
            and trade_quality.approved
        ):


            position_check = (
                self.position_filter.evaluate(
                    current_position=self.position_state,
                    new_direction=trend_context.allowed_direction,
                )
            )


            if not position_check.allowed:

                return TradingDecisionV2(
                    action=TradingActionV2.HOLD,
                    confidence=0.5,
                    reason=position_check.reason,
                )


            if trend_context.allowed_direction == "LONG":


                self.signal_controller.register_trade(
                    index=current_index,
                    direction="LONG",
                )


                return TradingDecisionV2(
                    action=TradingActionV2.BUY,
                    confidence=(
                        confluence.score / 100
                    ),
                    reason=(
                        f"A+ LONG | {confluence.grade}"
                    ),
                    metadata={
                        "stop_loss": entry_price - self.stop_loss_points,
                        "take_profit": entry_price + self.take_profit_points,                        "confluence_score": confluence.score / 100,
                        "grade": confluence.grade,
                        "reasons": confluence.reasons,
                    },
                )



            if trend_context.allowed_direction == "SHORT":


                self.signal_controller.register_trade(
                    index=current_index,
                    direction="SHORT",
                )


                return TradingDecisionV2(
                    action=TradingActionV2.SELL,
                    confidence=(
                        confluence.score / 100
                    ),
                    reason=(
                        f"A+ SHORT | {confluence.grade}"
                    ),
                    metadata={
                        "stop_loss": entry_price + self.stop_loss_points,
                        "take_profit": entry_price - self.take_profit_points,                        "confluence_score": confluence.score / 100,
                        "grade": confluence.grade,
                        "reasons": confluence.reasons,
                    },
                )



        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=(
                confluence.score / 100
            ),
            reason="NO A+ CONFLUENCE",
            metadata={
                "confluence_score": (
                    confluence.score / 100
                ),
                "grade": confluence.grade,
                "reasons": confluence.reasons,
            },
        )
