"""Canonical, immutable request model for the MEDAR cognitive core."""

from dataclasses import dataclass
from enum import Enum


class CognitiveDomain(str, Enum):
    GENERAL = "GENERAL"
    WEB_RESEARCH = "WEB_RESEARCH"
    CODING = "CODING"
    FINANCIAL = "FINANCIAL"
    TRADING = "TRADING"
    CRYPTO = "CRYPTO"
    PORTFOLIO = "PORTFOLIO"
    BUSINESS = "BUSINESS"
    MARKETING = "MARKETING"
    LIFE_ADVICE = "LIFE_ADVICE"
    ROSITA = "ROSITA"
    COMPUTER_ACTION = "COMPUTER_ACTION"
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"
    VOICE = "VOICE"
    UNKNOWN = "UNKNOWN"


class RiskClass(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TimeSensitivity(str, Enum):
    STATIC = "STATIC"
    CURRENT = "CURRENT"
    REALTIME = "REALTIME"


def normalize_user_input(value: str) -> str:
    """Normalize whitespace without changing the user's words or meaning."""

    if not isinstance(value, str):
        raise TypeError("request input must be text")
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("request input must not be blank")
    return normalized


@dataclass(frozen=True)
class CognitiveRequest:
    request_id: str
    conversation_id: str
    user_intent: str
    raw_input: str
    normalized_input: str
    domain: CognitiveDomain
    risk_class: RiskClass
    required_capabilities: tuple[str, ...]
    time_sensitivity: TimeSensitivity
    requires_web: bool = False
    requires_tools: bool = False
    requires_memory: bool = False
    requires_human_confirmation: bool = False

    def __post_init__(self) -> None:
        for name in ("request_id", "conversation_id", "user_intent"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        normalized = normalize_user_input(self.raw_input)
        if self.normalized_input != normalized:
            raise ValueError("normalized_input must equal canonical normalization")
        if not isinstance(self.domain, CognitiveDomain):
            raise TypeError("domain must be CognitiveDomain")
        if not isinstance(self.risk_class, RiskClass):
            raise TypeError("risk_class must be RiskClass")
        if not isinstance(self.time_sensitivity, TimeSensitivity):
            raise TypeError("time_sensitivity must be TimeSensitivity")
        if not isinstance(self.required_capabilities, tuple):
            raise TypeError("required_capabilities must be a tuple")
        if any(not isinstance(item, str) or not item.strip() for item in self.required_capabilities):
            raise ValueError("required capabilities must be non-empty text")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("required capabilities must be unique")
        for name in (
            "requires_web",
            "requires_tools",
            "requires_memory",
            "requires_human_confirmation",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
