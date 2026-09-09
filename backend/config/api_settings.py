import math
import os
from dataclasses import dataclass
from dataclasses import field






def _required_positive_finite_float(
    name: str,
) -> float:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        raise ValueError(
            f"{name} debe configurarse explícitamente "
            "con un número finito mayor que cero."
        )

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} debe ser un número finito "
            "mayor que cero."
        ) from exc

    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(
            f"{name} debe ser un número finito "
            "mayor que cero."
        )

    return value

def _required_non_negative_finite_float(
    name: str,
) -> float:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        raise ValueError(
            f"{name} debe configurarse explícitamente "
            "con un número finito mayor o igual que cero."
        )

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} debe ser un número finito "
            "mayor o igual que cero."
        ) from exc

    if not math.isfinite(value) or value < 0.0:
        raise ValueError(
            f"{name} debe ser un número finito "
            "mayor o igual que cero."
        )

    return value




def _required_positive_int(
    name: str,
) -> int:
    raw_value = os.getenv(name)

    if raw_value is None or not raw_value.strip():
        raise ValueError(
            f"{name} debe configurarse explícitamente "
            "con un entero mayor que cero."
        )

    normalized = raw_value.strip()

    try:
        value = int(normalized)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} debe ser un entero "
            "mayor que cero."
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} debe ser un entero "
            "mayor que cero."
        )

    return value


def _optional_environment_value(
    name: str,
) -> str | None:
    value = os.getenv(name)

    if value is None:
        return None

    normalized = value.strip()

    if not normalized:
        return None

    return normalized



def _required_unit_interval_float(
    environment_name: str,
) -> float:
    raw_value = os.getenv(environment_name)

    if raw_value is None or not raw_value.strip():
        raise ValueError(
            f"{environment_name} debe estar configurado."
        )

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{environment_name} debe ser numérico."
        ) from exc

    if not math.isfinite(value):
        raise ValueError(
            f"{environment_name} debe ser finito."
        )

    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{environment_name} debe estar entre 0.0 y 1.0."
        )

    return value


def _required_boolean(
    env_name: str,
) -> bool:
    raw_value = os.getenv(env_name)

    if raw_value is None:
        raise ValueError(
            f"{env_name} debe configurarse explícitamente "
            "como true/false, 1/0 o yes/no."
        )

    normalized = raw_value.strip().lower()

    truthy = {
        "true",
        "1",
        "yes",
    }

    falsy = {
        "false",
        "0",
        "no",
    }

    if normalized in truthy:
        return True

    if normalized in falsy:
        return False

    raise ValueError(
        f"{env_name} debe ser true/false, "
        "1/0 o yes/no."
    )


@dataclass(frozen=True)
class APISettings:
    """
    Configuración base de la API.
    """

    title: str = "ARMS AI API"
    version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    webhook_token: str = (
        os.getenv(
            "ARMS_WEBHOOK_TOKEN",
            "development-secret",
        )
    )

    certified_market_hours_path: str | None = field(
        default_factory=lambda: _optional_environment_value(
            "ARMS_CERTIFIED_MARKET_HOURS_PATH"
        )
    )
    certified_economic_news_path: str | None = field(
        default_factory=lambda: _optional_environment_value(
            "ARMS_CERTIFIED_ECONOMIC_NEWS_PATH"
        )
    )
    maximum_quote_age_seconds: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MAXIMUM_QUOTE_AGE_SECONDS"
        )
    )
    minimum_reward_risk_ratio: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MINIMUM_REWARD_RISK_RATIO"
        )
    )
    minimum_stop_points: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MINIMUM_STOP_POINTS"
        )
    )
    maximum_stop_points: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MAXIMUM_STOP_POINTS"
        )
    )
    maximum_spread_points: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MAXIMUM_SPREAD_POINTS"
        )
    )
    minimum_atr_points: float = field(
        default_factory=lambda: _required_positive_finite_float(
            "ARMS_MINIMUM_ATR_POINTS"
        )
    )
    minimum_a_plus_probability: float = field(
        default_factory=lambda: _required_unit_interval_float(
            "ARMS_MINIMUM_A_PLUS_PROBABILITY"
        )
    )
    minimum_execution_confidence: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MINIMUM_EXECUTION_CONFIDENCE"
            )
            if os.getenv(
                "ARMS_MINIMUM_EXECUTION_CONFIDENCE"
            )
            is not None
            else 0.70
        )
    )
    minimum_probability_approval: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MINIMUM_PROBABILITY_APPROVAL"
            )
            if os.getenv(
                "ARMS_MINIMUM_PROBABILITY_APPROVAL"
            )
            is not None
            else 0.80
        )
    )

    probability_very_high_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_PROBABILITY_VERY_HIGH_THRESHOLD"
            )
            if os.getenv(
                "ARMS_PROBABILITY_VERY_HIGH_THRESHOLD"
            ) is not None
            else 0.90
        )
    )
    probability_high_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_PROBABILITY_HIGH_THRESHOLD"
            )
            if os.getenv(
                "ARMS_PROBABILITY_HIGH_THRESHOLD"
            ) is not None
            else 0.80
        )
    )
    probability_medium_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_PROBABILITY_MEDIUM_THRESHOLD"
            )
            if os.getenv(
                "ARMS_PROBABILITY_MEDIUM_THRESHOLD"
            ) is not None
            else 0.65
        )
    )

    multi_timeframe_minimum_ready_weight: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MULTI_TIMEFRAME_MINIMUM_READY_WEIGHT"
            )
            if os.getenv(
                "ARMS_MULTI_TIMEFRAME_MINIMUM_READY_WEIGHT"
            ) is not None
            else 0.65
        )
    )
    multi_timeframe_neutral_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MULTI_TIMEFRAME_NEUTRAL_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MULTI_TIMEFRAME_NEUTRAL_THRESHOLD"
            ) is not None
            else 0.15
        )
    )
    multi_timeframe_conflict_weight_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MULTI_TIMEFRAME_CONFLICT_WEIGHT_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MULTI_TIMEFRAME_CONFLICT_WEIGHT_THRESHOLD"
            ) is not None
            else 0.25
        )
    )
    market_context_minimum_candles: int = field(
        default_factory=lambda: (
            _required_positive_int(
                "ARMS_MARKET_CONTEXT_MINIMUM_CANDLES"
            )
            if os.getenv(
                "ARMS_MARKET_CONTEXT_MINIMUM_CANDLES"
            ) is not None
            else 5
        )
    )
    market_context_internal_range_lookback: int = field(
        default_factory=lambda: (
            _required_positive_int(
                "ARMS_MARKET_CONTEXT_INTERNAL_RANGE_LOOKBACK"
            )
            if os.getenv(
                "ARMS_MARKET_CONTEXT_INTERNAL_RANGE_LOOKBACK"
            ) is not None
            else 10
        )
    )
    market_context_near_extreme_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_CONTEXT_NEAR_EXTREME_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_CONTEXT_NEAR_EXTREME_THRESHOLD"
            ) is not None
            else 0.10
        )
    )
    market_context_equilibrium_tolerance: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_CONTEXT_EQUILIBRIUM_TOLERANCE"
            )
            if os.getenv(
                "ARMS_MARKET_CONTEXT_EQUILIBRIUM_TOLERANCE"
            ) is not None
            else 0.05
        )
    )
    market_context_decision_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_CONTEXT_DECISION_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_CONTEXT_DECISION_THRESHOLD"
            ) is not None
            else 0.25
        )
    )

    multi_timeframe_dominance_margin: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MULTI_TIMEFRAME_DOMINANCE_MARGIN"
            )
            if os.getenv(
                "ARMS_MULTI_TIMEFRAME_DOMINANCE_MARGIN"
            ) is not None
            else 0.35
        )
    )

    trend_fast_period: int = field(
        default_factory=lambda: (
            _required_positive_int(
                "ARMS_TREND_FAST_PERIOD"
            )
            if os.getenv(
                "ARMS_TREND_FAST_PERIOD"
            ) is not None
            else 10
        )
    )
    trend_slow_period: int = field(
        default_factory=lambda: (
            _required_positive_int(
                "ARMS_TREND_SLOW_PERIOD"
            )
            if os.getenv(
                "ARMS_TREND_SLOW_PERIOD"
            ) is not None
            else 50
        )
    )
    trend_slope_lookback: int = field(
        default_factory=lambda: (
            _required_positive_int(
                "ARMS_TREND_SLOPE_LOOKBACK"
            )
            if os.getenv(
                "ARMS_TREND_SLOPE_LOOKBACK"
            ) is not None
            else 5
        )
    )
    trend_sideways_threshold_percent: float = field(
        default_factory=lambda: (
            _required_positive_finite_float(
                "ARMS_TREND_SIDEWAYS_THRESHOLD_PERCENT"
            )
            if os.getenv(
                "ARMS_TREND_SIDEWAYS_THRESHOLD_PERCENT"
            ) is not None
            else 0.0005
        )
    )

    trailing_stop_activation_points: float = field(
        default_factory=lambda: (
            _required_positive_finite_float(
                "ARMS_TRAILING_STOP_ACTIVATION_POINTS"
            )
            if os.getenv(
                "ARMS_TRAILING_STOP_ACTIVATION_POINTS"
            )
            is not None
            else 30.0
        )
    )

    trailing_stop_distance_points: float = field(
        default_factory=lambda: (
            _required_positive_finite_float(
                "ARMS_TRAILING_STOP_DISTANCE_POINTS"
            )
            if os.getenv(
                "ARMS_TRAILING_STOP_DISTANCE_POINTS"
            )
            is not None
            else 10.0
        )
    )

    paper_execution_fill_market_orders_immediately: bool = field(
        default_factory=lambda: (
            _required_boolean(
                "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
            )
            if os.getenv(
                "ARMS_PAPER_EXECUTION_FILL_MARKET_ORDERS_IMMEDIATELY"
            )
            is not None
            else True
        )
    )

    paper_execution_slippage_points: float = field(
        default_factory=lambda: (
            _required_non_negative_finite_float(
                "ARMS_PAPER_EXECUTION_SLIPPAGE_POINTS"
            )
            if os.getenv(
                "ARMS_PAPER_EXECUTION_SLIPPAGE_POINTS"
            )
            is not None
            else 0.25
        )
    )

    market_regime_trend_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_REGIME_TREND_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_REGIME_TREND_THRESHOLD"
            ) is not None
            else 0.60
        )
    )

    market_regime_high_volatility_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_REGIME_HIGH_VOLATILITY_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_REGIME_HIGH_VOLATILITY_THRESHOLD"
            ) is not None
            else 0.80
        )
    )

    market_regime_low_volatility_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_REGIME_LOW_VOLATILITY_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_REGIME_LOW_VOLATILITY_THRESHOLD"
            ) is not None
            else 0.20
        )
    )

    market_regime_compression_threshold: float = field(
        default_factory=lambda: (
            _required_unit_interval_float(
                "ARMS_MARKET_REGIME_COMPRESSION_THRESHOLD"
            )
            if os.getenv(
                "ARMS_MARKET_REGIME_COMPRESSION_THRESHOLD"
            ) is not None
            else 0.15
        )
    )

    minimum_a_plus_confluence_score: float = field(
        default_factory=lambda: _required_unit_interval_float(
            "ARMS_MINIMUM_A_PLUS_CONFLUENCE_SCORE"
        )
    )
    maximum_signal_age_seconds: int = field(
        default_factory=lambda: _required_positive_int(
            "ARMS_MAXIMUM_SIGNAL_AGE_SECONDS"
        )
    )
    maximum_open_positions: int = field(
        default_factory=lambda: _required_positive_int(
            "ARMS_MAXIMUM_OPEN_POSITIONS"
        )
    )

    signal_execution_cooldown_minutes: int = field(
        default_factory=lambda: int(
            os.getenv(
                "ARMS_SIGNAL_EXECUTION_COOLDOWN_MINUTES",
                "15",
            )
        )
    )


    break_even_trigger_profit_points: float = field(
        default_factory=lambda: float(
            os.getenv(
                "ARMS_BREAK_EVEN_TRIGGER_PROFIT_POINTS",
                "15.0",
            )
        )
    )

    break_even_offset_points: float = field(
        default_factory=lambda: float(
            os.getenv(
                "ARMS_BREAK_EVEN_OFFSET_POINTS",
                "1.0",
            )
        )
    )

    partial_take_profit_trigger_profit_points: float = field(
        default_factory=lambda: float(
            os.getenv(
                "ARMS_PARTIAL_TAKE_PROFIT_TRIGGER_PROFIT_POINTS",
                "20.0",
            )
        )
    )

    partial_take_profit_close_fraction: float = field(
        default_factory=lambda: float(
            os.getenv(
                "ARMS_PARTIAL_TAKE_PROFIT_CLOSE_FRACTION",
                "0.5",
            )
        )
    )

    def __post_init__(self) -> None:

        if (
            not math.isfinite(
                self.partial_take_profit_trigger_profit_points
            )
            or self.partial_take_profit_trigger_profit_points <= 0
        ):
            raise ValueError(
                "partial_take_profit_trigger_profit_points "
                "debe ser finito y mayor que cero."
            )

        if (
            not math.isfinite(
                self.partial_take_profit_close_fraction
            )
            or not (
                0.0
                < self.partial_take_profit_close_fraction
                < 1.0
            )
        ):
            raise ValueError(
                "partial_take_profit_close_fraction "
                "debe ser finita y estar estrictamente entre 0 y 1."
            )

        if (
            not math.isfinite(
                self.break_even_trigger_profit_points
            )
            or self.break_even_trigger_profit_points <= 0
        ):
            raise ValueError(
                "break_even_trigger_profit_points "
                "debe ser finito y mayor que cero."
            )

        if (
            not math.isfinite(
                self.break_even_offset_points
            )
            or self.break_even_offset_points < 0
        ):
            raise ValueError(
                "break_even_offset_points "
                "debe ser finito y mayor o igual que cero."
            )

        if (
            isinstance(
                self.signal_execution_cooldown_minutes,
                bool,
            )
            or not isinstance(
                self.signal_execution_cooldown_minutes,
                int,
            )
            or self.signal_execution_cooldown_minutes < 0
        ):
            raise ValueError(
                "signal_execution_cooldown_minutes "
                "debe ser un entero mayor o igual que cero."
            )

        if (
            not isinstance(
                self.maximum_quote_age_seconds,
                (int, float),
            )
            or isinstance(
                self.maximum_quote_age_seconds,
                bool,
            )
        ):
            raise TypeError(
                "maximum_quote_age_seconds debe ser numérico."
            )

        if self.maximum_quote_age_seconds <= 0.0:
            raise ValueError(
                "maximum_quote_age_seconds debe ser mayor que cero."
            )

        float_policy_fields = {
            "minimum_reward_risk_ratio": (
                self.minimum_reward_risk_ratio
            ),
            "minimum_stop_points": (
                self.minimum_stop_points
            ),
            "maximum_stop_points": (
                self.maximum_stop_points
            ),
            "maximum_spread_points": (
                self.maximum_spread_points
            ),
            "minimum_atr_points": (
                self.minimum_atr_points
            ),
        }

        for field_name, raw_value in (
            float_policy_fields.items()
        ):
            if (
                not isinstance(
                    raw_value,
                    (int, float),
                )
                or isinstance(
                    raw_value,
                    bool,
                )
            ):
                raise TypeError(
                    f"{field_name} debe ser numérico."
                )

            normalized = float(raw_value)

            if (
                not math.isfinite(normalized)
                or normalized <= 0.0
            ):
                raise ValueError(
                    f"{field_name} debe ser un número "
                    "finito mayor que cero."
                )

            object.__setattr__(
                self,
                field_name,
                normalized,
            )

        if (
            not isinstance(
                self.maximum_signal_age_seconds,
                int,
            )
            or isinstance(
                self.maximum_signal_age_seconds,
                bool,
            )
        ):
            raise TypeError(
                "maximum_signal_age_seconds "
                "debe ser entero."
            )

        if self.maximum_signal_age_seconds <= 0:
            raise ValueError(
                "maximum_signal_age_seconds "
                "debe ser mayor que cero."
            )

        if (
            self.maximum_stop_points
            < self.minimum_stop_points
        ):
            raise ValueError(
                "maximum_stop_points no puede ser "
                "menor que minimum_stop_points."
            )

        if not self.webhook_token.strip():
            raise ValueError(
                "webhook_token no puede estar vacío."
            )

        if (
            self.certified_market_hours_path
            is not None
            and not isinstance(
                self.certified_market_hours_path,
                str,
            )
        ):
            raise TypeError(
                "certified_market_hours_path debe ser "
                "str o None."
            )

        if self.certified_market_hours_path is not None:
            normalized_path = (
                self.certified_market_hours_path.strip()
            )

            if not normalized_path:
                normalized_path = None

            object.__setattr__(
                self,
                "certified_market_hours_path",
                normalized_path,
            )

        if (
            self.certified_economic_news_path
            is not None
            and not isinstance(
                self.certified_economic_news_path,
                str,
            )
        ):
            raise TypeError(
                "certified_economic_news_path debe ser "
                "str o None."
            )

        if self.certified_economic_news_path is not None:
            normalized_economic_news_path = (
                self.certified_economic_news_path.strip()
            )

            if not normalized_economic_news_path:
                normalized_economic_news_path = None

            object.__setattr__(
                self,
                "certified_economic_news_path",
                normalized_economic_news_path,
            )

        for field_name in (
            "minimum_a_plus_probability",
            "minimum_a_plus_confluence_score",
        ):
            value = float(getattr(self, field_name))

            if not math.isfinite(value):
                raise ValueError(
                    f"{field_name} debe ser finito."
                )

            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{field_name} debe estar entre "
                    "0.0 y 1.0."
                )

            object.__setattr__(
                self,
                field_name,
                value,
            )

        if (
            self.market_regime_low_volatility_threshold
            >= self.market_regime_high_volatility_threshold
        ):
            raise ValueError(
                "market_regime_low_volatility_threshold "
                "no puede ser mayor o igual que "
                "market_regime_high_volatility_threshold."
            )

        if (
            self.multi_timeframe_minimum_ready_weight
            <= 0
        ):
            raise ValueError(
                "multi_timeframe_minimum_ready_weight "
                "debe ser mayor que cero."
            )

        if (
            self.market_context_minimum_candles
            < 3
        ):
            raise ValueError(
                "market_context_minimum_candles "
                "debe ser mayor o igual que 3."
            )

        if (
            self.market_context_internal_range_lookback
            < 3
        ):
            raise ValueError(
                "market_context_internal_range_lookback "
                "debe ser mayor o igual que 3."
            )

        if (
            self.market_context_near_extreme_threshold
            <= 0
        ):
            raise ValueError(
                "market_context_near_extreme_threshold "
                "debe ser mayor que cero."
            )

        if (
            self.market_context_decision_threshold
            <= 0
        ):
            raise ValueError(
                "market_context_decision_threshold "
                "debe ser mayor que cero."
            )

        if (
            not isinstance(
                self.trend_fast_period,
                int,
            )
            or self.trend_fast_period <= 1
        ):
            raise ValueError(
                "trend_fast_period debe ser un entero "
                "mayor que 1."
            )

        if (
            not isinstance(
                self.trend_slow_period,
                int,
            )
            or self.trend_slow_period
            <= self.trend_fast_period
        ):
            raise ValueError(
                "trend_slow_period debe ser mayor que "
                "trend_fast_period."
            )

        if (
            not isinstance(
                self.trend_slope_lookback,
                int,
            )
            or self.trend_slope_lookback < 2
        ):
            raise ValueError(
                "trend_slope_lookback debe ser un entero "
                "mayor o igual que 2."
            )

        if (
            self.probability_medium_threshold
            > self.probability_high_threshold
        ):
            raise ValueError(
                "probability_medium_threshold "
                "no puede ser mayor que "
                "probability_high_threshold."
            )

        if (
            self.probability_high_threshold
            > self.minimum_probability_approval
        ):
            raise ValueError(
                "probability_high_threshold "
                "no puede ser mayor que "
                "minimum_probability_approval."
            )

        if (
            self.minimum_probability_approval
            > self.probability_very_high_threshold
        ):
            raise ValueError(
                "minimum_probability_approval "
                "no puede ser mayor que "
                "probability_very_high_threshold."
            )
