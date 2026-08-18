from fastapi import APIRouter, Request


from backend.intelligence.technical_intelligence_adapter import (
    TechnicalIntelligenceAdapter,
)


from backend.intelligence.market_structure_intelligence_adapter import (
    MarketStructureIntelligenceAdapter,
)


from backend.intelligence.risk_intelligence_adapter import (
    RiskIntelligenceAdapter,
)


from backend.intelligence.intelligence_data_provider import (
    IntelligenceDataProvider,
)


from backend.intelligence.confidence_intelligence_orchestrator_v3 import (
    ConfidenceIntelligenceOrchestratorV3,
)


from backend.intelligence.trade_execution_intelligence import (
    TradeExecutionIntelligence,
)


from backend.execution.execution_pipeline_v2 import (
    ExecutionPipelineV2,
)



router = APIRouter(

    prefix="/api/v3/dashboard",

    tags=[

        "ARMS AI Decision Engine V3"

    ],

)



technical_engine = TechnicalIntelligenceAdapter()

structure_engine = MarketStructureIntelligenceAdapter()

risk_engine = RiskIntelligenceAdapter()

provider = IntelligenceDataProvider()

orchestrator = ConfidenceIntelligenceOrchestratorV3()

execution_engine = TradeExecutionIntelligence()


execution_pipeline = None


def configure_execution_pipeline_v3(
    journal=None,
):

    global execution_pipeline


    execution_pipeline = (
        ExecutionPipelineV2(
            journal=journal
        )
    )




@router.get(
    "/intelligence-decision"
)
def intelligence_decision_v3():



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



    risk_report = risk_engine.analyze(

        account_size=150000,

        risk_percent=1,

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

    )



    intelligence_data = provider.collect(

        technical_report=technical_report,

        structure_report=structure_report,

        risk_report=risk_report,

        probability_score=90,

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



    trade_plan = execution_engine.analyze(

        symbol="NQ",

        direction="BUY",

        entry=23500,

        stop_loss=23450,

        take_profit=23650,

        account_size=150000,

        risk_percent=1,

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


        "execution_status":

            decision.execution_status,


        "risk_allowed":

            decision.risk_allowed,


        "risk_score":

            decision.risk_score,


        "sources":

            decision.sources,


        "reasoning":

            decision.reasoning,


        "trade_plan": {

            "entry":
                trade_plan.entry,

            "stop_loss":
                trade_plan.stop_loss,

            "take_profit":
                trade_plan.take_profit,

            "risk_amount":
                trade_plan.risk_amount,

            "reward_amount":
                trade_plan.reward_amount,

            "risk_reward_ratio":
                trade_plan.risk_reward_ratio,

            "contracts":
                trade_plan.contracts,

            "approved":
                trade_plan.approved,

        },


        "recommendations":

            decision.recommendations,


    }





@router.post(
    "/monitor-price-debug"
)
def monitor_price_debug_v3(request: Request):



    before_positions = (
        request.app.state
        .trade_lifecycle_service_v2
        .get_active_positions()
    )

    before_journal = (
        request.app.state
        .trade_journal_v2
        .get_trades()
    )

    result = (
        request.app.state
        .live_position_monitor_v2
        .process_price(
            symbol="NQ",
            current_price=23650,
        )
    )

    after_positions = (
        request.app.state
        .trade_lifecycle_service_v2
        .get_active_positions()
    )

    after_journal = (
        request.app.state
        .trade_journal_v2
        .get_trades()
    )


    return {
        "before_positions": before_positions,
        "before_journal": before_journal,

        "monitor_result": result,

        "after_positions": after_positions,
        "after_journal": after_journal,

        "active_positions_after":
            request.app.state
            .trade_lifecycle_service_v2
            .get_active_positions(),

        "journal":
            request.app.state
            .trade_journal_v2
            .get_trades(),

        "portfolio":
            request.app.state
            .portfolio_manager_v2
            .get_summary(),
    }



@router.get(
    "/position-debug"
)
def position_debug_v3(request: Request):



    return {
        "active_positions":
            request.app.state
            .trade_lifecycle_service_v2
            .get_active_positions(),

        "portfolio":
            request.app.state
            .portfolio_manager_v2
            .get_summary(),

        "journal":
            request.app.state
            .trade_journal_v2
            .get_trades(),
    }



@router.get(
    "/journal-debug"
)
def journal_debug_v3():

    if execution_pipeline is None:
        return {
            "error": "pipeline_not_configured"
        }


    trades = (
        execution_pipeline
        .journal
        .get_trades()
    )


    return {
        "trades": trades,
        "total": len(trades),
    }



@router.get(
    "/execution-pipeline"
)
def execution_pipeline_v3(request: Request):




    result = (
        request.app.state
        .trade_lifecycle_service_v2
        .submit_signal(
            signal={
                "symbol": "NQ",
                "direction": "LONG",
                "entry_price": 23500,
                "stop_loss": 23450,
                "take_profit": 23650,
                "contracts": 1,
                "approved": True,
                "decision": "SEND_SIGNAL",
                "signal_decision": "SEND",
                "probability": 90,
                "confluence_score": 95,
                "grade": "A+",
            },

            order_type="MARKET",

            risk_context={
                "point_value": 20,
                "current_price": 23500,
                "account_size": 150000,
            },

            order_context={
                "market_is_open": True,
            },
        )
    )


    return result


@router.post(
    "/market-price"
)
def market_price_v3(
    payload: dict,
    request: Request,
):



    result = (
        request.app.state
        .price_feed_service_v2
        .process_price(
            symbol=payload.get(
                "symbol",
                "NQ",
            ),
            current_price=float(
                payload.get(
                    "price"
                )
            ),
            source=payload.get(
                "source",
                "MANUAL",
            ),
        )
    )


    return result
