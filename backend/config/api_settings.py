import os
from dataclasses import dataclass
from dataclasses import field




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

    def __post_init__(self) -> None:
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
