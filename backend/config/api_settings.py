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

    def __post_init__(self) -> None:
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
