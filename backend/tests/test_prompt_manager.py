import pytest

from backend.ai.prompt_manager import (
    PromptManager,
)


def test_lists_available_prompts():
    prompts = (
        PromptManager()
        .available_prompts()
    )

    assert "portfolio_analysis" in prompts
    assert "risk_explanation" in prompts
    assert "executive_summary" in prompts


def test_renders_portfolio_analysis_prompt():
    result = PromptManager().render(
        name="portfolio_analysis",
        variables={
            "question": "Analiza mi portafolio.",
            "decision_summary": (
                "Riesgo moderado y score 82."
            ),
        },
    )

    assert "Analiza mi portafolio" in result
    assert "score 82" in result


def test_renders_system_prompt():
    result = (
        PromptManager()
        .system_prompt(
            role="financial_copilot"
        )
    )

    assert "ARMS-AI" in result
    assert "financiero" in result.lower()


def test_rejects_unknown_prompt():
    with pytest.raises(
        ValueError,
        match="prompt",
    ):
        PromptManager().render(
            name="unknown",
            variables={},
        )


def test_rejects_missing_variable():
    with pytest.raises(
        ValueError,
        match="variables",
    ):
        PromptManager().render(
            name="portfolio_analysis",
            variables={
                "question": "Analiza.",
            },
        )


def test_rejects_unknown_role():
    with pytest.raises(
        ValueError,
        match="role",
    ):
        PromptManager().system_prompt(
            role="unknown",
        )
