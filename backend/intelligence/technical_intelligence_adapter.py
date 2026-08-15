from dataclasses import dataclass
from typing import List



@dataclass
class TechnicalIntelligenceReport:

    technical_score: float

    trend: str

    momentum: str

    volatility: str

    reasoning: List[str]




class TechnicalIntelligenceAdapter:


    def __init__(self):

        pass



    def analyze(

        self,

        ema_signal: str,

        rsi_signal: str,

        atr_signal: str,

    ) -> TechnicalIntelligenceReport:



        score = 0

        reasoning = []



        # EMA TREND

        if ema_signal == "BULLISH":

            score += 40

            reasoning.append(
                "EMA confirma tendencia alcista."
            )

        elif ema_signal == "BEARISH":

            score += 40

            reasoning.append(
                "EMA confirma tendencia bajista."
            )

        else:

            reasoning.append(
                "EMA sin confirmación clara."
            )



        # RSI MOMENTUM

        if rsi_signal == "STRONG":

            score += 35

            reasoning.append(
                "RSI muestra momentum favorable."
            )

        elif rsi_signal == "NEUTRAL":

            score += 15

            reasoning.append(
                "RSI neutral."
            )

        else:

            reasoning.append(
                "RSI débil."
            )



        # ATR VOLATILITY

        if atr_signal == "GOOD":

            score += 25

            reasoning.append(
                "ATR con volatilidad adecuada."
            )

        else:

            reasoning.append(
                "ATR no ideal."
            )



        if score >= 85:

            trend = "STRONG"

        elif score >= 60:

            trend = "MEDIUM"

        else:

            trend = "WEAK"



        return TechnicalIntelligenceReport(

            technical_score=score,

            trend=trend,

            momentum=rsi_signal,

            volatility=atr_signal,

            reasoning=reasoning,

        )
