from dataclasses import dataclass

import pytest

from backend.ai.providers.base import (
    AIProvider,
    AIProviderResponse,
)


@dataclass
class FakeProvider(AIProvider):
    provider_name: str = "fake"

    def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AIProviderResponse:
        return AIProviderResponse(
            provider=self.provider_name,
            model="fake-model",
            content=(
                f"{system_prompt} | "
                f"{user_prompt}"
            ),
        )


def test_provider_returns_structured_response():
    result = FakeProvider().chat(
        system_prompt="Eres un analista.",
        user_prompt="Analiza el portafolio.",
    )

    assert result.provider == "fake"
    assert result.model == "fake-model"
    assert "Analiza" in result.content


def test_response_converts_to_dict():
    result = AIProviderResponse(
        provider="fake",
        model="fake-model",
        content="Respuesta",
    )

    assert result.to_dict() == {
        "provider": "fake",
        "model": "fake-model",
        "content": "Respuesta",
    }


def test_response_rejects_empty_provider():
    with pytest.raises(
        ValueError,
        match="provider",
    ):
        AIProviderResponse(
            provider="",
            model="fake-model",
            content="Respuesta",
        )


def test_response_rejects_empty_model():
    with pytest.raises(
        ValueError,
        match="model",
    ):
        AIProviderResponse(
            provider="fake",
            model="",
            content="Respuesta",
        )


def test_response_rejects_empty_content():
    with pytest.raises(
        ValueError,
        match="content",
    ):
        AIProviderResponse(
            provider="fake",
            model="fake-model",
            content="",
        )


def test_ai_provider_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AIProvider()
