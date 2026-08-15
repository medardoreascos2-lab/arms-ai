from dataclasses import dataclass


from backend.execution.trade_execution_simulator_v2 import (
    TradeExecutionSimulatorV2,
)


from backend.journal.trade_journal_v2 import (
    TradeJournalV2,
)


from backend.intelligence.trading_memory_service_v2 import (
    TradingMemoryServiceV2,
)



@dataclass
class ExecutionPipelineReport:

    trade_id: str

    symbol: str

    direction: str

    execution_status: str

    journal_status: str

    message: str




class ExecutionPipelineV2:



    def __init__(
        self,
        journal=None,
        memory_service=None,
    ):

        self.simulator = TradeExecutionSimulatorV2()


        self.journal = (
            journal
            if journal is not None
            else TradeJournalV2()
        )


        self.memory_service = (
            memory_service
            if memory_service is not None
            else TradingMemoryServiceV2()
        )


        self.counter = 0



    def execute(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        contracts: int,

        risk_amount: float,

        approved: bool,

    ) -> ExecutionPipelineReport:



        self.counter += 1


        trade_id = (

            f"ARMS-{self.counter:03d}"

        )



        simulated_trade = self.simulator.execute(

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            contracts=contracts,

            risk_amount=risk_amount,

            approved=approved,

        )



        if simulated_trade.status == "OPEN":


            journal_entry = self.journal.record(

                trade_id=trade_id,

                symbol=symbol,

                direction=direction,

                entry=entry,

                stop_loss=stop_loss,

                take_profit=take_profit,

                contracts=contracts,

                risk_amount=risk_amount,

                status="OPEN",

            )


            journal_status = "RECORDED"



        else:

            journal_status = "NOT_RECORDED"



        return ExecutionPipelineReport(

            trade_id=trade_id,

            symbol=symbol,

            direction=direction,

            execution_status=simulated_trade.status,

            journal_status=journal_status,

            message=(

                "Pipeline ejecutado correctamente."

            ),

        )
