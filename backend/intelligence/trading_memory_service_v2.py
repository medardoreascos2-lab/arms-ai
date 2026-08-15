from backend.intelligence.trading_memory_engine_v2 import (
    TradingMemoryEngineV2,
)



class TradingMemoryServiceV2:



    def __init__(self):

        self.memory = TradingMemoryEngineV2()



    def process_trade(

        self,

        symbol: str,

        direction: str,

        strategy: str,

        pnl: float,

    ):


        result = (

            "WIN"

            if pnl > 0

            else

            "LOSS"

        )


        return self.memory.analyze_trade(

            symbol=symbol,

            direction=direction,

            strategy=strategy,

            result=result,

            pnl=pnl,

        )




    def get_memory_report(self):

        return self.memory.analyze_memory()
