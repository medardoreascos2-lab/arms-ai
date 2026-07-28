from __future__ import annotations

from abc import ABC
from abc import abstractmethod


class BrokerConnectorV2(ABC):
    """
    Contrato común para conectores de ejecución.

    Las implementaciones concretas pueden representar
    entornos PAPER, SIM o LIVE, pero todas deben devolver
    estructuras compatibles con el pipeline institucional.
    """

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Nombre normalizado del broker o entorno."""

    @property
    @abstractmethod
    def execution_mode(self) -> str:
        """Modo PAPER, SIM o LIVE."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Indica si el conector está disponible."""

    @abstractmethod
    def connect(self) -> dict[str, object]:
        """Inicia la conexión."""

    @abstractmethod
    def disconnect(self) -> dict[str, object]:
        """Finaliza la conexión."""

    @abstractmethod
    def health_check(self) -> dict[str, object]:
        """Devuelve el estado operativo del conector."""

    @abstractmethod
    def submit_order(
        self,
        *,
        prepared_order: dict[str, object],
        client_order_id: str | None = None,
    ) -> dict[str, object]:
        """Envía una orden preparada."""

    @abstractmethod
    def modify_order(
        self,
        *,
        order_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        limit_price: float | None = None,
    ) -> dict[str, object]:
        """Modifica parámetros de una orden existente."""

    @abstractmethod
    def cancel_order(
        self,
        *,
        order_id: str,
    ) -> dict[str, object]:
        """Cancela una orden pendiente."""

    @abstractmethod
    def close_position(
        self,
        *,
        position_id: str,
        current_price: float,
        reason: str,
    ) -> dict[str, object]:
        """Solicita el cierre de una posición."""

    @abstractmethod
    def get_account(self) -> dict[str, object]:
        """Devuelve la información de la cuenta."""

    @abstractmethod
    def get_positions(self) -> list[dict[str, object]]:
        """Devuelve posiciones conocidas por el conector."""

    @abstractmethod
    def get_orders(self) -> list[dict[str, object]]:
        """Devuelve órdenes conocidas por el conector."""

    @abstractmethod
    def get_fills(self) -> list[dict[str, object]]:
        """Devuelve ejecuciones o fills conocidos."""
