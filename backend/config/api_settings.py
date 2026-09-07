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
