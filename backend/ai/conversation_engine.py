from __future__ import annotations

from backend.ai.ai_decision_engine import (
    AIDecisionEngine,
)
from backend.ai.prompt_manager import (
    PromptManager,
)
from backend.ai.providers.base import (
    AIProvider,
)


class ConversationEngine:
    """
    Orquesta el motor de decisiones,
    el administrador de prompts
    y el proveedor de inteligencia artificial.
    """

    def __init__(
        self,
        *,
        provider: AIProvider | None,
        decision_engine: AIDecisionEngine
        | None = None,
        prompt_manager: PromptManager
        | None = None,
    ) -> None:
        if provider is None:
            raise ValueError(
                "provider no puede ser None."
            )

        self.provider = provider

        self.decision_engine = (
            decision_engine
            or AIDecisionEngine()
        )

        self.prompt_manager = (
            prompt_manager
            or PromptManager()
        )

    def ask(
        self,
        *,
        question: str,
        weights: dict[str, float],
        metrics: dict[str, float],
    ) -> dict[str, object]:
        normalized_question = (
            str(question)
            .strip()
        )

        if not normalized_question:
            raise ValueError(
                "question no puede estar vacío."
            )

        decision = (
            self.decision_engine.analyze(
                weights=weights,
                metrics=metrics,
            )
        )

        system_prompt = (
            self.prompt_manager.system_prompt(
                role="financial_copilot"
            )
        )

        user_prompt = (
            self.prompt_manager.render(
                name="portfolio_analysis",
                variables={
                    "question": (
                        normalized_question
                    ),
                    "decision_summary": (
                        decision[
                            "summary"
                        ]
                    ),
                },
            )
        )

        provider_response = (
            self.provider.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        )

        return {
            "provider": (
                provider_response.provider
            ),
            "model": (
                provider_response.model
            ),
            "content": (
                provider_response.content
            ),
            "decision": decision,
        }
