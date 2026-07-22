from __future__ import annotations

from backend.ai.providers.base import (
    AIProvider,
    AIProviderResponse,
)


class LocalAIProvider(AIProvider):
    """
    Proveedor local determinístico para desarrollo,
    pruebas y funcionamiento sin APIs externas.
    """

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIProviderResponse:
        del system_prompt

        return AIProviderResponse(
            provider="arms-ai-local",
            model="decision-engine-v1",
            content=(
                "Análisis generado por ARMS-AI: "
                f"{user_prompt}"
            ),
        )
