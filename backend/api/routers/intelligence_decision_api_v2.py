from fastapi import APIRouter


from backend.intelligence.technical_intelligence_adapter import (
    TechnicalIntelligenceAdapter,
)


from backend.intelligence.market_structure_intelligence_adapter import (
    MarketStructureIntelligenceAdapter,
)


from backend.intelligence.intelligence_data_provider import (
    IntelligenceDataProvider,
)


from backend.intelligence.confidence_intelligence_orchestrator_v2 import (
    ConfidenceIntelligenceOrchestratorV2,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Intelligence Decision Core"

    ],

)



technical_engine = TechnicalIntelligenceAdapter()

structure_engine = MarketStructureIntelligenceAdapter()

provider = IntelligenceDataProvider()

orchestrator = ConfidenceIntelligenceOrchestratorV2()



@router.get(
    "/intelligence-decision"
)
def intelligence_decision_dashboard():


    technical_report = technical_engine.analyze(

        ema_signal="BULLISH",

        rsi_signal="STRONG",

        atr_signal="GOOD",

    )



    structure_report = structure_engine.analyze(

        bos_confirmed=True,

        choch_confirmed=True,

        fvg_present=True,

        session_aligned=True,

        trend="BULLISH",

    )



    intelligence_data = provider.collect(

        technical_report=technical_report,

        structure_report=structure_report,

        probability_score=90,

        risk_score=100,

        memory_score=100,

    )



    decision = orchestrator.analyze(

        symbol="NQ",

        direction="BUY",

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

        intelligence_data=intelligence_data,

    )



    return {


        "symbol":
            decision.symbol,


        "direction":
            decision.direction,


        "entry":
            decision.entry,


        "stop_loss":
            decision.stop_loss,


        "take_profit":
            decision.take_profit,


        "confidence":
            decision.final_confidence,


        "quality":
            decision.quality,


        "decision":
            decision.decision,


        "sources":
            decision.sources,


        "reasoning":
            decision.reasoning,


        "recommendations":
            decision.recommendations,


    }
