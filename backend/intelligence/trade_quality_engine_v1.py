from dataclasses import dataclass


@dataclass
class TradeQualityResultV1:

    score: float

    approved: bool

    reasons: list[str]



class TradeQualityEngineV1:
    """
    Motor de calidad de entrada ARMS AI.

    Evalúa si una señal merece ejecución.
    """


    def evaluate(
        self,
        *,
        confluence,
        market_structure,
        trend_context,
    ) -> TradeQualityResultV1:


        score = 0

        reasons = []


        # ======================================
        # HARD STRUCTURE PROTECTION
        # ======================================

        if market_structure.choch:

            return TradeQualityResultV1(
                score=0,
                approved=False,
                reasons=[
                    "Opposite CHOCH detected",
                ],
            )


        # Confluence

        if confluence.grade == "A+":

            score += 40

            reasons.append(
                "A+ Confluence"
            )


        # Market Structure

        if market_structure.structure in (
            "HH_HL",
            "LH_LL",
        ):

            score += 20

            reasons.append(
                "Valid market structure"
            )


        # BOS

        if market_structure.bos:

            score += 15

            reasons.append(
                "Break Of Structure"
            )


        # CHOCH protection

        if not market_structure.choch:

            score += 15

            reasons.append(
                "No opposite CHOCH"
            )


        # HTF alignment

        if trend_context.aligned:

            score += 10

            reasons.append(
                "HTF aligned"
            )


        return TradeQualityResultV1(

            score=min(
                score,
                100,
            ),

            approved=score >= 85,

            reasons=reasons,

        )
