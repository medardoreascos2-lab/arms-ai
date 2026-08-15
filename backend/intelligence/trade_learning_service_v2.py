from backend.analysis.trade_outcome_analyzer_v2 import (
    TradeOutcomeAnalyzerV2,
)


from backend.intelligence.trading_memory_service_v2 import (
    TradingMemoryServiceV2,
)



class TradeLearningServiceV2:



    def __init__(self):

        self.outcome_analyzer = TradeOutcomeAnalyzerV2()

        self.memory_service = TradingMemoryServiceV2()



    def process_closed_trade(

        self,

        trade_id: str,

        symbol: str,

        direction: str,

        strategy: str,

        entry: float,

        exit_price: float,

        contracts: int,

        real_pnl: float | None = None,

    ):


        outcome = self.outcome_analyzer.analyze(

            trade_id=trade_id,

            symbol=symbol,

            direction=direction,

            entry=entry,

            exit_price=exit_price,

            contracts=contracts,

            real_pnl=real_pnl,

        )



        self.memory_service.process_trade(

            symbol=symbol,

            direction=direction,

            strategy=strategy,

            pnl=outcome.pnl,

        )



        return outcome



    def get_learning_report(self):

        return self.memory_service.get_memory_report()
