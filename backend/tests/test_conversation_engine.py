from dataclasses import dataclass

import pytest

from backend.ai.conversation_engine import (
    ConversationEngine,
)
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
                "Respuesta generada con contexto: "
                f"{system_prompt} | {user_prompt}"
            ),
        )


def build_weights() -> dict[str, float]:
    return {
        "AAPL": 0.50,
        "MSFT": 0.30,
        "NVDA": 0.20,
    }


def build_metrics() -> dict[str, float]:
    return {
        "volatility": 0.22,
        "sharpe_ratio": 0.75,
        "beta": 1.20,
        "drawdown": -0.18,
    }


def test_returns_conversational_response():
    result = ConversationEngine(
        provider=FakeProvider(),
    ).ask(
        question="Analiza mi portafolio.",
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert result["provider"] == "fake"
    assert result["model"] == "fake-model"
    assert "content" in result
    assert "decision" in result


def test_includes_decision_payload():
    result = ConversationEngine(
        provider=FakeProvider(),
    ).ask(
        question="Analiza mi portafolio.",
        weights=build_weights(),
        metrics=build_metrics(),
    )

    decision = result["decision"]

    assert "score" in decision
    assert "risk_level" in decision
    assert "recommendations" in decision
    assert "alerts" in decision


def test_provider_receives_rendered_prompt():
    result = ConversationEngine(
        provider=FakeProvider(),
    ).ask(
        question="¿Cómo reduzco el riesgo?",
        weights=build_weights(),
        metrics=build_metrics(),
    )

    assert "¿Cómo reduzco el riesgo?" in result["content"]
    assert "puntuación" in result["content"].lower()


def test_rejects_empty_question():
    with pytest.raises(
        ValueError,
        match="question",
    ):
        ConversationEngine(
            provider=FakeProvider(),
        ).ask(
            question="",
            weights=build_weights(),
            metrics=build_metrics(),
        )


def test_rejects_missing_provider():
    with pytest.raises(
        ValueError,
        match="provider",
    ):
        ConversationEngine(
            provider=None,
        )
