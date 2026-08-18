from dataclasses import dataclass


@dataclass
class PositionFilterResult:

    allowed: bool

    reason: str



class PositionFilterV1:
    """
    Control de posición ARMS AI.

    Evita:
    - Entradas repetidas
    - Sobreoperación
    - Añadir posiciones iguales
    """


    def evaluate(
        self,
        *,
        current_position,
        new_direction,
    ) -> PositionFilterResult:


        if current_position == "FLAT":

            return PositionFilterResult(
                allowed=True,
                reason="NO ACTIVE POSITION",
            )


        if (
            current_position == "LONG"
            and new_direction == "LONG"
        ):

            return PositionFilterResult(
                allowed=False,
                reason="ALREADY LONG",
            )


        if (
            current_position == "SHORT"
            and new_direction == "SHORT"
        ):

            return PositionFilterResult(
                allowed=False,
                reason="ALREADY SHORT",
            )


        return PositionFilterResult(
            allowed=False,
            reason="CLOSE EXISTING POSITION FIRST",
        )
