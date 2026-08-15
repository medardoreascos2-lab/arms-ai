from backend.brokers.paper_broker import (
    PaperBroker,
)


class OrderRouter:


    def __init__(self):

        self.broker = PaperBroker()



    def route_order(
        self,
        order
    ):


        return self.broker.submit_order(
            order
        )
