from fastapi import APIRouter

from backend.ai.ai_decision_engine import (
    AIDecisionEngine,
)
from backend.ai.conversation_engine import (
    ConversationEngine,
)
from backend.ai.providers.local_provider import (
    LocalAIProvider,
)
from backend.api.schemas.ai import (
    AICopilotRequest,
    AIDecisionRequest,
)


router = APIRouter(
    prefix="/ai",
    tags=["ai"],
)


@router.post("/decision")
def analyze_ai_decision(
    request: AIDecisionRequest,
) -> dict[str, object]:
    return AIDecisionEngine().analyze(
        weights=request.weights,
        metrics=request.metrics,
    )


@router.post("/copilot")
def ask_ai_copilot(
    request: AICopilotRequest,
) -> dict[str, object]:
    return ConversationEngine(
        provider=LocalAIProvider(),
    ).ask(
        question=request.question,
        weights=request.weights,
        metrics=request.metrics,
    )
