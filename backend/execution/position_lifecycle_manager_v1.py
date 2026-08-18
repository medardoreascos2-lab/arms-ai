from dataclasses import dataclass


@dataclass
class PositionLifecycleResult:

    status: str

    closed: bool

    pnl: float



class PositionLifecycleManagerV1:
    """
    Gestor del ciclo de vida de posiciones ARMS AI.

    Controla:

    - Entrada
    - TP
    - SL
    - Cierre
    - Reset de estado
    """


    def __init__(self):

        self.position = "FLAT"

        self.entry_price = None

        self.stop_loss = None

        self.take_profit = None



    def open_position(
        self,
        *,
        direction,
        entry_price,
        stop_loss,
        take_profit,
    ):

        self.position = direction

        self.entry_price = entry_price

        self.stop_loss = stop_loss

        self.take_profit = take_profit



        return PositionLifecycleResult(
            status="OPEN",
            closed=False,
            pnl=0,
        )



    def update(
        self,
        current_price,
    ):


        if self.position == "FLAT":

            return PositionLifecycleResult(
                status="NO POSITION",
                closed=False,
                pnl=0,
            )



        pnl = 0



        if self.position == "LONG":


            if current_price >= self.take_profit:

                pnl = (
                    self.take_profit
                    -
                    self.entry_price
                )

                return self.close(
                    pnl
                )


            if current_price <= self.stop_loss:

                pnl = (
                    self.stop_loss
                    -
                    self.entry_price
                )

                return self.close(
                    pnl
                )



        if self.position == "SHORT":


            if current_price <= self.take_profit:

                pnl = (
                    self.entry_price
                    -
                    self.take_profit
                )

                return self.close(
                    pnl
                )


            if current_price >= self.stop_loss:

                pnl = (
                    self.entry_price
                    -
                    self.stop_loss
                )

                return self.close(
                    pnl
                )



        return PositionLifecycleResult(
            status="ACTIVE",
            closed=False,
            pnl=0,
        )



    def close(
        self,
        pnl,
    ):

        self.position = "FLAT"

        self.entry_price = None

        self.stop_loss = None

        self.take_profit = None


        return PositionLifecycleResult(
            status="CLOSED",
            closed=True,
            pnl=pnl,
        )
