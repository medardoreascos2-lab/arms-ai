from dataclasses import dataclass


@dataclass
class SignalControlResult:

    allowed: bool

    reason: str



class SignalControllerV1:
    """
    Controla frecuencia de señales ARMS AI.

    Evita:
    - entradas repetidas
    - sobreoperación
    - señales consecutivas iguales
    """


    def __init__(
        self,
        cooldown_bars: int = 20,
    ):

        self.cooldown_bars = cooldown_bars

        self.last_trade_index = None

        self.last_direction = None



    def evaluate(
        self,
        *,
        current_index: int,
        direction: str,
    ) -> SignalControlResult:


        if self.last_trade_index is None:

            return SignalControlResult(
                allowed=True,
                reason="FIRST SIGNAL",
            )


        bars_since_trade = (
            current_index
            -
            self.last_trade_index
        )


        if bars_since_trade < self.cooldown_bars:

            return SignalControlResult(
                allowed=False,
                reason=(
                    "SIGNAL COOLDOWN ACTIVE"
                ),
            )


        if direction == self.last_direction:

            return SignalControlResult(
                allowed=False,
                reason=(
                    "DUPLICATE DIRECTION"
                ),
            )


        return SignalControlResult(
            allowed=True,
            reason="NEW VALID SIGNAL",
        )



    def register_trade(
        self,
        *,
        index: int,
        direction: str,
    ):

        self.last_trade_index = index

        self.last_direction = direction
