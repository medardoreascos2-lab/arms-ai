from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AIProviderResponse:
    provider: str
    model: str
    content: str

    def __post_init__(self) -> None:
        normalized_provider = (
            str(self.provider)
            .strip()
        )

        normalized_model = (
            str(self.model)
            .strip()
        )

        normalized_content = (
            str(self.content)
            .strip()
        )

        if not normalized_provider:
            raise ValueError(
                "provider no puede estar vacío."
            )

        if not normalized_model:
            raise ValueError(
                "model no puede estar vacío."
            )

        if not normalized_content:
            raise ValueError(
                "content no puede estar vacío."
            )

        object.__setattr__(
            self,
            "provider",
            normalized_provider,
        )

        object.__setattr__(
            self,
            "model",
            normalized_model,
        )

        object.__setattr__(
            self,
            "content",
            normalized_content,
        )

    def to_dict(
        self,
    ) -> dict[str, str]:
        return {
            "provider": self.provider,
            "model": self.model,
            "content": self.content,
        }


class AIProvider(ABC):
    """
    Contrato común para cualquier proveedor
    de inteligencia artificial.
    """

    @abstractmethod
    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIProviderResponse:
        raise NotImplementedError
