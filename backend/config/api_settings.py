import os
from dataclasses import dataclass


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

    def __post_init__(self) -> None:
        if not self.webhook_token.strip():
            raise ValueError(
                "webhook_token no puede estar vacío."
            )
