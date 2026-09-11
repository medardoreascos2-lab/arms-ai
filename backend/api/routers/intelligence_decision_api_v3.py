from dataclasses import asdict, is_dataclass

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
def intelligence_decision_v3(request: Request):

    active_risk_profile = (
        request.app.state
        .account_config_manager_v2
        .get_active_account()
    )

    risk_percent = float(
        active_risk_profile.risk_percent
    )

    active_account_size = float(
        active_risk_profile.account_size
    )



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

        account_size=active_account_size,

        risk_percent=risk_percent,

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

        account_size=active_account_size,

        risk_percent=risk_percent,

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



def _read_pipeline_records(reader):
    """Copy an existing read model; unavailable data must never trigger execution."""
    if not callable(reader):
        return None
    try:
        records = reader()
        if not isinstance(records, list):
            return None
        snapshot = []
        for record in records:
            if is_dataclass(record) and not isinstance(record, type):
                record = asdict(record)
            if not isinstance(record, dict):
                return None
            snapshot.append(dict(record))
        return snapshot
    except Exception:
        # A failed read is unavailable, never an invitation to generate a trade.
        return None


def _pipeline_text(record, field):
    value = record.get(field)
    return value.strip() if isinstance(value, str) and value.strip() else None


@router.get(
    "/execution-pipeline"
)
def execution_pipeline_v3(request: Request):
    """Observe existing activity only. No signals, risk evaluation or commands."""
    positions = _read_pipeline_records(
        getattr(
            getattr(request.app.state, "trade_lifecycle_service_v2", None),
            "get_active_positions",
            None,
        )
    )
    trades = _read_pipeline_records(
        getattr(
            getattr(request.app.state, "trade_journal_v2", None),
            "get_trades",
            None,
        )
    )
    snapshot = {
        "status": "UNAVAILABLE",
        "source": None,
        "position_id": None,
        "trade_id": None,
        "symbol": None,
        "direction": None,
        "execution_status": "UNAVAILABLE",
        "journal_status": "UNAVAILABLE",
        "message": "Datos del pipeline no disponibles o incompletos.",
    }
    if positions == [] and trades == []:
        return {
            **snapshot,
            "status": "IDLE",
            "execution_status": "IDLE",
            "journal_status": "NOT_RECORDED",
            "message": "Sin actividad existente en el pipeline.",
        }

    record = None
    journal_record = None
    if positions:
        record = positions[-1]
        snapshot["source"] = "position"
        position_id = _pipeline_text(record, "position_id")
        if trades is not None and position_id:
            journal_record = next(
                (trade for trade in reversed(trades)
                 if _pipeline_text(trade, "position_id") == position_id),
                None,
            )
            if journal_record is not None:
                snapshot["journal_status"] = "RECORDED"
            elif all(_pipeline_text(trade, "position_id") for trade in trades):
                snapshot["journal_status"] = "NOT_RECORDED"
    elif trades:
        record = journal_record = trades[-1]
        snapshot["source"] = "journal"
        if (_pipeline_text(record, "trade_id")
                or _pipeline_text(record, "position_id")):
            snapshot["journal_status"] = "RECORDED"

    if record is not None:
        snapshot.update({
            "position_id": _pipeline_text(record, "position_id"),
            "trade_id": (
                _pipeline_text(journal_record, "trade_id")
                if journal_record is not None else None
            ),
            "symbol": _pipeline_text(record, "symbol"),
            "direction": _pipeline_text(record, "direction"),
            "execution_status": _pipeline_text(record, "status") or "UNAVAILABLE",
        })
        if (
            positions is not None
            and trades is not None
            and (snapshot["position_id"] or snapshot["trade_id"])
            and snapshot["symbol"]
            and snapshot["direction"]
            and snapshot["execution_status"] != "UNAVAILABLE"
            and snapshot["journal_status"] != "UNAVAILABLE"
        ):
            snapshot["status"] = "AVAILABLE"
            snapshot["message"] = (
                "Estado observado de la posición existente."
                if snapshot["source"] == "position"
                else "Último registro existente en el journal."
            )
    return snapshot


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
