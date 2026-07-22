from pydantic import BaseModel


class AIDecisionRequest(BaseModel):
    weights: dict[str, float]
    metrics: dict[str, float]


class AICopilotRequest(BaseModel):
    question: str
    weights: dict[str, float]
    metrics: dict[str, float]
