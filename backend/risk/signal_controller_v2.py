from dataclasses import dataclass


@dataclass
class SignalControlResult:

    allowed: bool

    reason: str



class SignalControllerV2:
    """
    Control inteligente de frecuencia
    de señales ARMS AI.

    Evita:
    - sobreoperación
    - entradas consecutivas iguales
    - ruido de mercado

    Permite:
    - cambio de dirección
    - nuevas oportunidades A+
    """


    def __init__(
        self,
        cooldown_bars: int = 10,
    ):

        self.cooldown_bars = cooldown_bars

        self.last_trade_index = None

        self.last_direction = None

        self.last_result = None



    def evaluate(
        self,
        *,
        current_index: int,
        direction: str,
        grade: str = "A",
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


        if (
            bars_since_trade
            <
            self.cooldown_bars
            and
            direction == self.last_direction
        ):

            return SignalControlResult(
                allowed=False,
                reason="SAME DIRECTION COOLDOWN",
            )


        if direction != self.last_direction:

            return SignalControlResult(
                allowed=True,
                reason="DIRECTION CHANGE",
            )


        if grade == "A+":

            return SignalControlResult(
                allowed=True,
                reason="NEW A+ SETUP",
            )


        return SignalControlResult(
            allowed=False,
            reason="WAITING",
        )



    def register_trade(
        self,
        *,
        index: int,
        direction: str,
        result: str = None,
    ):

        self.last_trade_index = index

        self.last_direction = direction

        self.last_result = result
