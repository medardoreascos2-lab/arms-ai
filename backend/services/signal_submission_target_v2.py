from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SignalSubmissionTargetV2(ABC):
    """
    Contrato para cualquier componente capaz
    de recibir una señal de trading.
    """

    @abstractmethod
    def submit_signal(
        self,
        *,
        signal: dict[str, object],
        order_type: str,
        risk_context: dict[str, object] | None = None,
        order_context: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        """
        Envía una señal al destino configurado.
        """
        raise NotImplementedError
