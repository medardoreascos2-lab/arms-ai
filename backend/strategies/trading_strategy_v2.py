from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TradingActionV2(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(slots=True)
class TradingDecisionV2:
    action: TradingActionV2
    confidence: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:

        if not isinstance(
            self.action,
            TradingActionV2,
        ):
            raise TypeError(
                "action debe ser un TradingActionV2."
            )

        if not (
            0.0 <= self.confidence <= 1.0
        ):
            raise ValueError(
                "confidence debe estar entre 0.0 y 1.0."
            )

        if not self.reason.strip():
            raise ValueError(
                "reason no puede estar vacío."
            )


class TradingStrategyV2(ABC):

    @abstractmethod
    def evaluate(
        self,
        context,
    ) -> TradingDecisionV2:
        """
        Evalúa el contexto del mercado y devuelve
        una decisión estructurada.
        """
        raise NotImplementedError
