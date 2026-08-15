from dataclasses import dataclass
from typing import List



@dataclass
class RiskIntelligenceReport:

    risk_score: float

    risk_amount: float

    reward_amount: float

    risk_reward_ratio: float

    position_allowed: bool

    reasoning: List[str]




class RiskIntelligenceAdapter:


    def __init__(self):

        pass



    def analyze(

        self,

        account_size: float,

        risk_percent: float,

        entry: float,

        stop_loss: float,

        take_profit: float,

    ) -> RiskIntelligenceReport:



        reasoning = []



        risk_amount = (

            account_size

            *

            risk_percent

            /

            100

        )



        stop_distance = abs(

            entry - stop_loss

        )


        reward_distance = abs(

            take_profit - entry

        )



        if stop_distance > 0:

            risk_reward_ratio = round(

                reward_distance / stop_distance,

                2

            )

        else:

            risk_reward_ratio = 0





        score = 0



        # RISK CONTROL

        if risk_percent <= 1:

            score += 40

            reasoning.append(

                "Riesgo por operación dentro del límite."

            )

        else:

            reasoning.append(

                "Riesgo por operación elevado."

            )





        # RISK REWARD

        if risk_reward_ratio >= 2:

            score += 40

            reasoning.append(

                "Relación riesgo beneficio favorable."

            )

        else:

            reasoning.append(

                "Relación riesgo beneficio insuficiente."

            )





        # STOP VALIDATION

        if stop_distance > 0:

            score += 20

            reasoning.append(

                "Stop Loss válido."

            )





        position_allowed = score >= 70





        return RiskIntelligenceReport(

            risk_score=score,

            risk_amount=risk_amount,

            reward_amount=(

                reward_distance

                *

                risk_amount

                /

                stop_distance

                if stop_distance > 0

                else 0

            ),

            risk_reward_ratio=risk_reward_ratio,

            position_allowed=position_allowed,

            reasoning=reasoning,

        )
