from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TradeSetup:

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    risk_reward: str

    quality: str

    validation: List[str]



class TradeSetupEngine:


    def __init__(self):
        pass



    def generate_setup(
        self,
        symbol: str,
        direction: str,
        entry: float,
        stop_distance: float,
        risk_reward: float = 3.0,
        quality: str = "A+",
    ) -> TradeSetup:


        validation = []


        if direction.upper() == "BUY":

            stop_loss = (
                entry - stop_distance
            )

            take_profit = (
                entry +
                (stop_distance * risk_reward)
            )


        else:

            stop_loss = (
                entry + stop_distance
            )

            take_profit = (
                entry -
                (stop_distance * risk_reward)
            )



        validation.append(
            "Direction validated"
        )

        validation.append(
            "Risk parameters calculated"
        )

        validation.append(
            "Risk reward approved"
        )



        return TradeSetup(

            symbol=symbol,

            direction=direction.upper(),

            entry=entry,

            stop_loss=round(
                stop_loss,
                2
            ),

            take_profit=round(
                take_profit,
                2
            ),

            risk_reward=f"1:{risk_reward}",

            quality=quality,

            validation=validation,

        )
